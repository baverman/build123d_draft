import functools
import math
from typing import Any, Collection, Sequence, Iterable

import OCP  # type: ignore[import-untyped]
from OCP.BRep import BRep_Tool  # type: ignore[import-untyped]

from build123d.geometry import Vector, Pos, Location, Plane, Axis, RotationLike, VectorLike
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
from build123d.objects_sketch import Rectangle, Circle as Circle_orig, SlotCenterPoint
from build123d.objects_part import Cylinder as Cylinder_orig
from build123d.build_common import LocationList
from build123d.objects_curve import Line
from build123d.build_enums import Align, Mode, Align2D, Align3D

from .utils import _defined

SAlign2D = Align | tuple[Align, Align]
SAlign3D = Align | tuple[Align, Align, Align]

__all__ = [
    'aligned',
    'axis_plane',
    'axis_offset',
    'cbore',
    'cbore_d',
    'Circle',
    'Cylinder',
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
    'PPos',
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


def ext_point_with_circle_intersection(p: VectorLike, c: Circle_orig) -> ShapeList[Vertex]:
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


class Cylinder(Cylinder_orig):
    def __init__(
        self,
        radius: float,
        height: float | None = None,
        arc_size: float = 360,
        rotation: RotationLike = (0, 0, 0),
        align: SAlign3D = (
            Align.CENTER,
            Align.CENTER,
            Align.CENTER,
        ),
        mode: Mode = Mode.ADD,
        d: float | None = None,
        r: float | None = None,
    ) -> None:
        if d is not None:
            h = radius
            radius = d / 2
        elif r is not None:
            h = radius
            radius = r
        else:
            assert height
            h = height
        super().__init__(radius, h, arc_size=arc_size, rotation=rotation, align=align, mode=mode)

    def new(
        self,
        radius: float | None = None,
        height: float | None = None,
        d: float | None = None,
        r: float | None = None,
    ) -> Cylinder:
        if d is not None:
            if radius is not None:
                height = radius
            radius = d / 2
        elif r is not None:
            if radius is not None:
                height = radius
            radius = r
        if height is None:
            height = self.cylinder_height
        assert radius
        return self.location * Cylinder(radius, height, align=self.align)


class Circle(Circle_orig):
    align: tuple[Align, Align]

    def __init__(
        self,
        radius: float | None = None,
        align: SAlign2D = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
        d: float | None = None,
    ):
        if d is not None:
            radius = d / 2
        assert radius
        super().__init__(radius, align=align, mode=mode)

    def cylinder(
        self,
        height: float,
        d: float | None = None,
        r: float | None = None,
        align: SAlign3D = Align.MIN,
    ) -> Cylinder:
        radius = self.radius
        if d is not None:
            radius = d / 2
        elif r is not None:
            radius = r
        za = tuplify(align, 3)[2]  # type: ignore[index]
        align = self.align[0], self.align[1], za
        return self.location * Cylinder(radius, height, align=align)


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
    wire: Wire, point: Vector | Sequence[float], normalized: bool = True
) -> float | None:
    edges = wire.edges()
    U = 0.0
    candidates: list[tuple[float, float]] = []
    pt = Vector(point).to_pnt()
    for e in edges:
        c, pr = edge_curve(e)
        poc = OCP.GeomAPI.GeomAPI_ProjectPointOnCurve(pt, c)
        p = poc.LowerDistanceParameter()
        if pr[0] <= p <= pr[1]:
            candidates.append((poc.LowerDistance(), U + abs(pr[int(not e.is_forward)] - p)))
        U += abs(pr[0] - pr[1])

    if not candidates:
        return None

    candidates.sort()
    u = candidates[0][1]
    if normalized:
        return u / U
    return u


def trim_wire(wire: Wire, start: float = 0, end: float = 1) -> Wire:
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


class PPos(Pos):
    def __init__(
        self, X: float | None = None, Y: float | None = None, Z: float | None = None
    ) -> None:
        super().__init__()
        self._initial = (X, Y, Z)

    def combine_abs(self, v: Iterable[float] | None) -> Vector:
        if v is None:
            v = Vector(0, 0, 0)

        r: list[float] = [0, 0, 0]
        for idx, (iv, vv) in enumerate(zip(self._initial, v)):
            r[idx] = iv if iv is not None else vv

        return Vector(*r)


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
