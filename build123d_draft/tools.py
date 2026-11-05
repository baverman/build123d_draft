import functools
import math
from dataclasses import dataclass, replace
from typing import Any, Collection, Sequence

import OCP  # type: ignore[import-untyped]
from OCP.BRep import BRep_Tool  # type: ignore[import-untyped]
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge  # type: ignore[import-untyped]
from OCP.Geom2d import Geom2d_TrimmedCurve  # type: ignore[import-untyped]
from OCP.Precision import Precision  # type: ignore[import-untyped]

from build123d.geometry import Vector, Pos, Location, Plane, Axis, VectorLike
from build123d.topology import (
    Wire,
    Edge,
    ShapeList,
    tuplify,
    new_edges,
    Part,
    Shape,
    Vertex,
    Compound,
    isclose_b,
)
from build123d.topology.shape_core import TOPODS
from build123d.operations_generic import mirror, split, MirrorType
from build123d.operations_part import extrude
from build123d.objects_sketch import Rectangle, Circle, SlotCenterPoint
from build123d.build_common import LocationList
from build123d.objects_curve import Line
from build123d.build_enums import Align, Align2D, Align3D

from .utils import _defined

SAlign2D = Align | tuple[Align, Align]
SAlign3D = Align | tuple[Align, Align, Align]

__all__ = [
    'AX',
    'AY',
    'aligned',
    'axis_plane',
    'axis_offset',
    'cbore',
    'cbore_d',
    'ext_point_with_circle_intersection',
    'fillet_tool',
    'force_fillet',
    'intersection',
    'intersections',
    'LocPart',
    'make_axis',
    'make_hslot',
    'make_slot',
    'mirror_add',
    'new_edges_add',
    'O',
    'overshoot_line',
    'plane_along',
    'point_on_axis_with_dist',
    'replace_vec',
    'reversed_wire',
    'param_on_point',
    'trim_wire',
]

O = Vector(0, 0, 0)


def replace_vec(
    v: Vector, X: float | None = None, Y: float | None = None, Z: float | None = None
) -> Vector:
    v = Vector(v)
    if X is not None:
        v.X = X
    if Y is not None:
        v.Y = Y
    if Z is not None:
        v.Z = Z
    return v


def fillet_tool(r: float, length: float, align: SAlign2D) -> Part:
    return extrude(Rectangle(r * 2, r * 2) - Circle(r, align=align), length)


def ext_point_with_circle_intersection(p: VectorLike, c: Circle) -> ShapeList[Vertex]:
    l = Line([c.center(), p])
    cc = Pos(l @ 0.5) * Circle(l.length / 2)
    return (c & cc).vertices()


def axis_plane(axis: Axis) -> Plane:
    return Plane(origin=axis.position, z_dir=axis.direction)


def plane_along(axis: Axis, raxis: Axis = Axis.Z) -> Plane:
    return Plane(origin=axis.position, z_dir=axis.direction.rotate(raxis, 90))


def point_on_axis_with_dist(start: Vector, axis: Axis, dist: float, raxis: Axis = Axis.Z) -> Vector:
    vp = start.project_to_plane(plane_along(axis, raxis))
    d1 = (vp - start).length
    d2: float = (dist * dist - d1 * d1) ** 0.5
    return vp + axis.direction * d2


def make_axis(start: Vector | Wire | Plane, end: Vector | None = None) -> Axis:
    if isinstance(start, Wire):
        s, e = start @ 0, start @ 1
    elif isinstance(start, Plane):
        return Axis(start.origin, start.z_dir)
    else:
        assert end
        s, e = start, end
    return Axis(s, e - s)


def overshoot_line(p1: Vector, p2: Vector, start: float = 0, end: float = 0) -> Line:
    d = (p2 - p1).normalized()
    return Line(p1 - d * start, p2 + d * end)


def intersections(shape: Shape[Any], other: Axis | Edge, tolerance: float = 0) -> ShapeList[Vector]:
    r: ShapeList[Vector] = ShapeList()
    for e in shape.edges():
        r.extend(e.find_intersection_points(other, tolerance=tolerance))
    return r


def dist(a: Vector | Shape[Any], b: Vector | Shape[Any]) -> float:
    if isinstance(a, Shape):
        return a.distance_to(b)
    elif isinstance(b, Shape):
        return b.distance_to(a)
    else:
        return (b - a).length


def intersection(
    shape: Shape[Any],
    other: Axis | Edge,
    near_by: Vector | Shape[Any] | None = None,
    tolerance: float = 0,
) -> Vector:
    # TODO: near_by could be declarative like 'end', 'start', 'center'
    # or a param coordinate to specify point on shape instead of fixing
    # it to the end as now
    r = intersections(shape, other, tolerance=tolerance)
    ref = near_by or shape.e
    points = sorted(r, key=lambda x: dist(x, ref))
    return points[0]


def cbore(r1: float, depth1: float, r2: float, total_depth: float) -> Part:
    return extrude(Circle(r1), -depth1) + Pos(Z=-depth1) * extrude(Circle(r2), depth1 - total_depth)


def cbore_d(d1: float, depth1: float, d2: float, total_depth: float) -> Part:
    return cbore(d1 / 2, depth1, d2 / 2, total_depth)


def mirror_add(obj: MirrorType, about: Plane = Plane.XZ) -> Compound:
    return obj + mirror(obj, about)


def aligned(obj: Shape[TOPODS], align: Align2D | Align3D) -> Shape[TOPODS]:
    align = tuplify(align, 2)
    return obj.moved(Location(Vector(*obj.bounding_box().to_align_offset(align))))


def new_edges_add(*parts: Compound) -> tuple[Compound, ShapeList[Edge]]:
    c = parts[0] + parts[1:]
    return c, new_edges(*parts, combined=c)


def force_fillet(part: Shape[Any], edges: Collection[Edge], radius: float) -> Part:
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet  # type: ignore[import-untyped]

    native_edges = [e.wrapped for e in edges]
    fillet_builder = BRepFilletAPI_MakeFillet(part.wrapped)
    for native_edge in native_edges:
        fillet_builder.Add(radius, native_edge)
    return Part(fillet_builder.Shape())


class LocPart(Part):
    center_locs: LocationList


def make_slot(
    length: float | tuple[float, float] | None = None,
    center: bool | float | Vector | None = True,
    end: float | Vector | None = None,
    start: float | Vector = O,
    r: float | None = None,
    h: float | None = None,
    d: float | None = None,
    rotation: float = 0,
    align: Align2D | Align3D | None = None,
    both: bool = False,
    half: bool = False,
) -> LocPart:
    sw = None
    if r is not None:
        sw = r * 2
    elif d is not None:
        sw = d
    assert sw, 'slot width required, use r or d arguments'

    nlength: float | None
    if isinstance(length, tuple):
        if center:
            start, center = length
            nlength = abs(start - center) * 2
        else:
            start, end = length
            nlength = abs(start - end)
    else:
        nlength = length

    if isinstance(start, (int, float)):
        nstart = Vector(start, 0, 0)
    else:
        assert start
        nstart = start

    ncenter: Vector
    if center is None or center is False:
        assert nlength is not None
        ncenter = nstart + Vector(nlength / 2 - sw / 2)
    elif end is not None:
        if isinstance(end, (int, float)):
            end = Vector(end)
        ncenter = nstart + end - Vector(sw / 2)
    elif center is True:
        assert nlength is not None
        ncenter = nstart + Vector(nlength / 2)
    else:
        if isinstance(center, (int, float)):
            ncenter = Vector(center, 0, 0)
        else:
            ncenter = center

    sk = SlotCenterPoint(nstart, ncenter, sw, rotation=rotation)
    if align:
        sk = aligned(sk, align)

    if h is None:
        rv = sk
        center_locs = LocationList([Pos(ncenter), Pos(nstart - (ncenter - nstart))])
    else:
        rv = extrude(sk, h, both=both)
        z = h / 2 + abs(h / 2)
        center_locs = LocationList(
            [Pos(replace_vec(ncenter, Z=z)), Pos(replace_vec(nstart - (ncenter - nstart), Z=z))]
        )

    if half:
        z_dir = (ncenter - nstart).normalized()
        x_dir = z_dir.rotate(Axis.Z, 90)
        rv = split(rv, Plane(nstart, x_dir=x_dir, z_dir=z_dir))

    rv.center_locs = center_locs
    return rv


make_hslot = functools.partial(make_slot, half=True)


def reversed_wire(wire: Wire) -> Wire:
    elist = []
    for e in wire.edges():
        elist.append(e.reversed())
    w = Wire(reversed(elist))
    return w


def edge_curve(edge: Edge) -> tuple[object, tuple[float, float]]:
    p1, p2 = BRep_Tool.Range_s(edge.wrapped)
    c = BRep_Tool.Curve_s(edge.wrapped, p1, p2)
    return c, (p1, p2)


def param_on_point(
    wire: Wire | Edge, point: Vector | Sequence[float], normalized: bool = True
) -> float | None:
    if isinstance(wire, Edge):
        edges = [wire]
    else:
        edges = wire.edges()
    U = 0.0
    candidates: list[tuple[float, float]] = []
    pt = Vector(point).to_pnt()
    for e in edges:
        c, pr = edge_curve(e)
        poc = OCP.GeomAPI.GeomAPI_ProjectPointOnCurve(pt, c)
        p = poc.LowerDistanceParameter()
        if pr[0] <= p <= pr[1] or isclose_b(pr[0], p) or isclose_b(pr[1], p):
            candidates.append((poc.LowerDistance(), U + abs(pr[int(not e.is_forward)] - p)))
        U += abs(pr[0] - pr[1])

    if not candidates:
        return None

    candidates.sort()
    u = candidates[0][1]
    if normalized:
        return u / U
    return u


def trim_wire(wire: Wire | Edge, start: float = 0, end: float = 1) -> Wire:
    if isinstance(wire, Edge):
        edges = [wire]
    else:
        edges = wire.edges()

    curves = [(it, edge_curve(it)) for it in edges]
    U = sum(abs(pr[0] - pr[1]) for _, (_, pr) in curves)
    start *= U
    end *= U

    nedges = []
    u2: float = 0
    for e, (c, pr) in curves:
        is_reversed = not e.is_forward
        u1 = u2
        u2 = u1 + abs(pr[0] - pr[1])
        if u2 < start or u1 > end:
            continue

        t1, t2 = pr
        if u1 <= start <= u2:
            d = start - u1
            if is_reversed:
                t2 -= d
            else:
                t1 += d

        if u1 <= end <= u2:
            d = u2 - end
            if is_reversed:
                t1 += d
            else:
                t2 -= d

        if isclose_b(t1, pr[0]) and isclose_b(t2, pr[1]):
            nedges.append(e.wrapped)
            continue

        if isclose_b(t1, t2):
            continue

        tc = OCP.Geom.Geom_TrimmedCurve(c, t1, t2)
        nedges.append(OCP.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(tc).Edge())
        if is_reversed:
            nedges[-1].Reverse()

    assert nedges

    rv = Wire([Edge(it) for it in nedges])

    return rv


def axis_offset(
    axis: Axis, X: float | Vector | tuple[float, ...] = 0, Y: float = 0, Z: float = 0
) -> Axis:
    if isinstance(X, (tuple, Vector)):
        v = X
    else:
        v = Vector(X, Y, Z)
    return Axis(axis.position + v, axis.direction)


def sagitta_arc(plane: Plane, start: Vector, end: Vector, sagitta: float) -> Edge:
    mid_point = (end + start) * 0.5
    sagitta_vector: Vector = (end - start).normalized() * abs(sagitta)
    sagitta_vector = sagitta_vector.rotate(make_axis(plane), 90 if sagitta > 0 else -90)
    sag_point = mid_point + sagitta_vector
    return Edge.make_three_point_arc(start, sag_point, end)


def radius_arc(plane: Plane, start: Vector, end: Vector, radius: float, short: bool = True) -> Edge:
    length = end.sub(start).length / 2.0
    try:
        if short:
            sagitta = abs(radius) - math.sqrt(radius**2 - length**2)
        else:
            sagitta = -abs(radius) - math.sqrt(radius**2 - length**2)
    except ValueError as exception:
        raise ValueError('Arc radius is not large enough to reach the end point.') from exception

    if radius > 0:
        return sagitta_arc(plane, start, end, sagitta)
    else:
        return sagitta_arc(plane, start, end, -sagitta)


def approx_edge(plane: Plane, curve: object, prange: tuple[float, float]) -> Edge:
    trimmed = Geom2d_TrimmedCurve(curve, *prange)

    approx = OCP.Geom2dConvert.Geom2dConvert_ApproxCurve(
        trimmed,
        1e-6,
        OCP.GeomAbs.GeomAbs_Shape.GeomAbs_C1,
        100,
        8,
    )

    if not approx.IsDone():
        raise RuntimeError('Offset approximation failed')

    result3d = OCP.GeomAPI.GeomAPI.To3d_s(approx.Curve(), plane.wrapped)
    return Edge(BRepBuilderAPI_MakeEdge(result3d).Edge())


def to_curve2d(edge: Edge, plane: Plane) -> tuple[object, tuple[float, float]]:
    p1, p2 = BRep_Tool.Range_s(edge.wrapped)
    curve3d = BRep_Tool.Curve_s(edge.wrapped, p1, p2)
    curve2d = OCP.GeomAPI.GeomAPI.To2d_s(curve3d, plane.wrapped)

    first = curve2d.FirstParameter()
    last = curve2d.LastParameter()
    if Precision.IsInfinite_s(first) or Precision.IsInfinite_s(last):
        curve2d = Geom2d_TrimmedCurve(curve2d, p1, p2)

    return curve2d, (p1, p2)


# def tangent_point(tangent: Edge, center: Vector) -> tuple[Vector, Vector]:
#     """Return the contact point on tangent curve closest to center and its tangent."""
#     _, point, _ = tangent.distance_to_with_closest_points(center)
#     param = tangent.param_at_point(point)
#
#     # param_at_point() uses the underlying curve parameter, while tangent_at()
#     # follows the edge orientation. Evaluate on a forward copy and flip if needed.
#     forward = tangent if tangent.is_forward else tangent.reversed()
#     direction = forward.tangent_at(param)
#     if not tangent.is_forward:
#         direction = -direction
#
#     return point, direction


def tangent_center(
    tangent: Edge | Axis, center_on: Edge | Axis, radius: float, plane: Plane
) -> tuple[float | None, Vector, Vector] | None:
    cpoints: list[Vector] = []
    if isinstance(tangent, Axis):
        normal_axis = Axis(plane.origin, plane.z_dir)
        off_axis = RelAxis(
            position=tangent.position, direction=tangent.direction, normal_axis=normal_axis
        )(radius).to_axis()
        ip = off_axis.intersect(center_on)
        if isinstance(ip, Vector):
            cpoints.append(ip)
        elif isinstance(ip, ShapeList):
            cpoints.extend(Vector(it) for it in ip.vertices())
    elif isinstance(center_on, Axis):
        cpoints.extend(tangent.intersect(center_on) or [])
    else:
        tcurve, _tprange = to_curve2d(tangent, plane)
        off_tcurve = OCP.Geom2d.Geom2d_OffsetCurve(tcurve, -radius)
        ccurve, _cprange = to_curve2d(center_on, plane)
        inter = OCP.Geom2dAPI.Geom2dAPI_InterCurveCurve(off_tcurve, ccurve)

        for i in range(1, inter.NbPoints() + 1):
            p = inter.Point(i)
            c = Vector(p.X(), p.Y()).transform(plane.reverse_transform)
            cpoints.append(c)

    if not cpoints:
        return None

    if isinstance(tangent, Axis):
        vcandidates = []
        for it in cpoints:
            vcandidates.append(project_to_axis(tangent, it) - tangent.position)

        d = tangent.direction
        vcandidates.sort(key=lambda x: (x.dot(d) < 0, x.length))
        vc = vcandidates[0]
        return None, tangent.position + vc, tangent.direction
    else:
        candidates = []
        for c in cpoints:
            # v, t = tangent_point(tangent, c)
            p = param_on_point(tangent, c)
            if p:
                candidates.append(p)

        candidates.sort()
        p = candidates[0]
        return p, tangent.position_at(p), tangent.tangent_at(p)


def intersect_circle(
    plane: Plane, center: Vector, radius: float, other: Axis | Edge
) -> tuple[Vector, Vector] | None:
    full_c = Edge.make_circle(abs(radius), plane.shift_origin(center))
    slist = full_c.intersect(other)
    if not slist:
        return None
    ic = [Vector(it) for it in slist.vertices()]
    icn = []
    for it in ic:
        itv = Vector(it)
        itp = param_on_point(full_c, itv)
        if itp is None:
            continue
        itt = full_c.tangent_at(itp)
        if radius < 0:
            itt = -itt
        if isinstance(other, Axis):
            cont = other.direction
        else:
            cont = other.tangent_at(itv)
        ndot = plane.z_dir.dot(cont.cross(itt))
        icn.append((ndot < 0, itv, itt))

    icn.sort()
    if icn and (len(icn) == 1 or not icn[0][0]):
        return icn[0][1], icn[0][2]

    return None


def to_vector(plane: Plane, v: Vector | tuple[float, ...], is_dir: bool = False) -> Vector:
    if isinstance(v, tuple):
        return Vector(v).transform(plane.reverse_transform, is_direction=is_dir)
    return v


@dataclass(frozen=True)
class RelAxis:
    direction: Vector
    normal_axis: Axis
    normal_side: int = 1
    position: Vector = Vector(0, 0, 0)

    def __call__(self, amount: float | Vector | tuple[float, ...]) -> RelAxis:
        if isinstance(amount, (float, int)):
            v = (
                self.normal_axis.direction.cross(self.direction).normalized()
                * amount
                * self.normal_side
            )
        else:
            v = Vector(amount)
        return replace(self, position=self.position + v)

    def rotate(self, amount: float) -> RelAxis:
        direction = self.direction.rotate(self.normal_axis, amount)
        return replace(self, direction=direction)

    def to_axis(self, plane: Plane | None = None) -> Axis:
        result = Axis(self.position, self.direction)
        if plane is not None:
            result = result.located(plane.location)
        return result


AX = RelAxis(direction=Vector(1, 0, 0), normal_axis=Axis.Z)
AY = RelAxis(direction=Vector(0, 1, 0), normal_side=-1, normal_axis=Axis.Z)


def project_to_axis(ax: Axis, v: Vector) -> Vector:
    d = ax.direction.normalized()
    return ax.position + d * (v - ax.position).dot(d)
