import functools
from build123d.geometry import Vector, Pos, Location, Plane, Axis, RotationLike
from build123d.topology import Wire, Edge, ShapeList, tuplify, new_edges, Part, Shape
from build123d.operations_generic import mirror, split
from build123d.operations_part import extrude
from build123d.objects_sketch import Rectangle, Circle, SlotCenterPoint
from build123d.objects_part import Cylinder
from build123d.build_common import LocationList
from build123d.objects_curve import Line
from build123d.build_enums import Align, Mode

from . import O
from .utils import _defined


def fillet_tool(r, length, align):
    return extrude(Rectangle(r*2, r*2) - Circle(r, align=align), length)


def ext_point_with_circle_intersection(p, c):
    Edge.make_circle()
    l = Line([c.center(), p])
    cc = Pos(l @ 0.5) * Circle(l.length / 2)
    return (c & cc).vertices()


def plane_along(axis, raxis=Axis.Z):
    return Axis(axis.position, axis.direction.rotate(raxis, 90)).to_plane()


def point_on_axis_with_dist(start, axis, dist, raxis=Axis.Z):
    vp = start.project_to_plane(plane_along(axis, raxis))
    d1 = abs(vp - start)
    d2 = (dist*dist - d1*d1)**0.5
    return vp + axis.direction * d2


def make_axis(start, end=None):
    if isinstance(start, Wire):
        start, end = start @ 0, start @ 1
    elif isinstance(start, Plane):
        return Axis(start.origin, start.z_dir)
    return Axis(start, end - start)


def overshoot_line(p1, p2, start=0, end=0):
    d = (p2 - p1).normalized()
    return Line(p1 - d * start, p2 + d * end)


def intersections(shape, other, tolerance=0):
    r = []
    for e in shape.edges():
        # print('### X', e.center(), other)
        r.extend(e.find_intersection_points(other, tolerance=tolerance))
    return ShapeList(r)


def dist(a, b):
    if isinstance(a, Shape):
        return a.distance_to(b)
    elif isinstance(b, Shape):
        return b.distance_to(a)
    else:
        return (b - a).length


def intersection(shape, other, near_by=None, tolerance=0):
    # TODO: near_by could be declarative like 'end', 'start', 'center'
    # or a param coordinate to specify point on shape instead of fixing
    # it to the end as now
    r = intersections(shape, other, tolerance=tolerance)
    ref = near_by or shape.e
    points = sorted(r, key=lambda x: dist(x, ref))
    return points[0]


def cbore(r1, depth1, r2, total_depth):
    return extrude(Circle(r1), -depth1) + Pos(Z=-depth1) * extrude(Circle(r2), depth1-total_depth)


def cbore_d(d1, depth1, d2, total_depth):
    return cbore(d1/2, depth1, d2/2, total_depth)


def mirror_add(obj, about=Plane.XZ):
    return obj + mirror(obj, about)


def aligned(obj, align):
    align = tuplify(align, 2)
    return obj.moved(Location(Vector(*obj.bounding_box().to_align_offset(align))))


def new_edges_add(*parts):
    # c = parts[0].fuse(*parts[1:])
    # c.clean()
    c = parts[0] + parts[1:]
    # print(c.show_topology())
    return c, new_edges(*parts, combined=c)


Cylinder_orig = Cylinder
Circle_orig = Circle


class Cylinder(Cylinder_orig):
    def __init__(
        self,
        radius: float,
        height: float | None = None,
        arc_size: float = 360,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] = (
            Align.CENTER,
            Align.CENTER,
            Align.CENTER,
        ),
        mode: Mode = Mode.ADD,
        d: float | None = None,
        r: float | None = None,
    ):
        if d is not None:
            height = radius
            radius = d/2
        elif r is not None:
            height = radius
            radius = r
        super().__init__(radius, height, arc_size=arc_size, rotation=rotation, align=align, mode=mode)

    def new(self, radius=None, height=None, d=None, r=None):
        if d is not None:
            if radius is not None:
                height = radius
            radius = d/2
        elif r is not None:
            if radius is not None:
                height = radius
            radius = r
        if height is None:
            height = self.cylinder_height
        return self.location * Cylinder(radius, height, align=self.align)


class Circle(Circle_orig):
    def __init__(
        self,
        radius: float | None = None,
        align: Align | tuple[Align, Align] = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
        d: float | None = None,
    ):
        if d is not None:
            radius = d/2
        super().__init__(radius, align=align, mode=mode)

    def cylinder(self, height, d=None, r=None, align=Align.MIN):
        radius = self.radius
        if d is not None:
            radius = d/2
        elif r is not None:
            radius = r
        align = self.align[0], self.align[1], tuplify(align, 3)[2]
        return self.location * Cylinder(radius, height, align=align)


def force_fillet(part, edges, radius):
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    native_edges = [e.wrapped for e in edges]
    fillet_builder = BRepFilletAPI_MakeFillet(part.wrapped)
    for native_edge in native_edges:
        fillet_builder.Add(radius, native_edge)
    return Part(fillet_builder.Shape())


def make_slot(length=None, center=True, end=None, start=O, r=None, h=None,
              d=None, rotation=None, align=None, both=False, half=False):
    sw = None
    if r is not None:
        sw = r*2
    elif d is not None:
        sw = d
    assert sw, 'slot width required, use r or d arguments'

    if isinstance(length, tuple):
        if center:
            start, center = length
        else:
            start, end = length

    if isinstance(start, (int, float)):
        start = Vector(start, 0, 0)

    if center is None or center is False:
        assert _defined(length)
        center = start + Vector(length/2-sw/2)
    elif end is not None:
        if isinstance(end, (int, float)):
            end = Vector(end)
        center = start + end - Vector(sw/2)
    elif center is True:
        assert _defined(length)
        center = start + Vector(length/2)
    else:
        if isinstance(center, (int, float)):
            center = Vector(center, 0, 0)

    sk = SlotCenterPoint(start, center, sw, rotation=rotation)
    if align:
        sk = aligned(sk, align)

    if h is None:
        rv = sk
        center_locs = LocationList(
            [Pos(center), Pos(start - (center - start))])
    else:
        rv = extrude(sk, h, both=both)
        z = h/2 + abs(h/2)
        center_locs = LocationList(
            [Pos(center, Z=z), Pos(start - (center - start), Z=z)])

    if half:
        z_dir = (center - start).normalized()
        x_dir = z_dir.rot(90, Axis.Z)
        rv = split(rv, Plane(start, x_dir=x_dir, z_dir=z_dir))

    rv.center_locs = center_locs
    return rv


make_hslot = functools.partial(make_slot, half=True)
