import math
from itertools import chain as it_chain

from build123d.geometry import Plane, Axis, Pos, Vector, Location
from build123d.topology import Shape, ShapeList, Wire, Edge
from build123d.objects_curve import Line, IntersectingLine, BaseLineObject, TangentArc, RadiusArc, CenterArc
from build123d.operations_sketch import make_face
from build123d.operations_generic import mirror, sweep, fillet, chamfer
from build123d.operations_part import extrude, revolve

from .utils import FakeBuilder, PPos, _defined, _defined_all, param_on_point, trim_wire
from .tools import make_axis, intersection

b123_mirror = mirror


class build_line:
    def __init__(self, start=None, plane=Plane.XY, tangent=None):
        # TODO: use context to get current plane
        if isinstance(start, Plane):
            start, plane = None, start
        self.plane = plane
        self._shapes = []
        self._named = {}
        if start is None:
            self._start_point = plane.origin
        else:
            self._start_point = self.to_vector(start, plane.origin)

        if tangent is None:
            self._start_tangent = plane.x_dir
        else:
            self._start_tangent = self.to_direction(tangent)

        self._builder = FakeBuilder(plane)

    def to_vector(self, v, ref=None):
        if isinstance(v, Pos):
            if ref is None:
                ref = self.e
            ref = ref.transform(self.plane.forward_transform)
            if isinstance(v, PPos):
                rv = v.combine_abs(ref)
            else:
                rv = v.position + ref
            return rv.transform(self.plane.reverse_transform)
        if isinstance(v, Axis):
            return v.position.transform(self.plane.reverse_transform)
        elif isinstance(v, tuple):
            return Vector(*v).transform(self.plane.reverse_transform)

        return v

    def to_direction(self, v):
        if isinstance(v, Pos):
            v = v.position.to_tuple()

        if isinstance(v, Vector):
            return v
        elif isinstance(v, Axis):
            return v.located(self.plane.location).direction
        elif isinstance(v, tuple):
            origin = self.to_vector((0, 0, 0))
            return self.to_vector(v) - origin

        assert False, f'Unsupported type {type(v)}'

    def apply(self, op):
        if isinstance(op, (Vector, Pos, tuple)):
            v = self.to_vector(op)
            self._shapes.append(Line(self.e, v))
        elif isinstance(op, Shape):
            self._shapes.append(op)
        else:
            s = op.fn(self, *op.args, **op.kwargs)
            if op.name:
                s._lb_name = op.name
                self._named[op.name] = s
            if op.reverse:
                chains = self.chains()
                for it in chains[-1]:
                    it.wrapped.Reverse()
                rv = list(it_chain.from_iterable(chains[:-1]))
                # rv.extend(reversed_wire(it) for it in reversed(chains[-1]))
                rv.extend(reversed(chains[-1]))
                self._shapes = rv
            if op.connect:
                chains = self.chains()
                if len(chains) > 1:
                    rv = list(it_chain.from_iterable(chains[:-1]))
                    rv.append(Line(rv[-1].e, chains[-1][0].s))
                    rv.extend(chains[-1])
                    self._shapes = rv

    def append(self, *ops):
        for op in ops:
            self.apply(op)
        return self

    @property
    def e(self):
        if self._shapes:
            return self._shapes[-1] @ 1
        else:
            return self._start_point

    @property
    def s(self):
        return self._shapes[0] @ 0

    @property
    def ss(self):
        return self._shapes[0] @ 1

    @property
    def ee(self):
        return self._shapes[-1] @ 0

    def wire(self):
        if len(self._shapes) == 1:
            return self._shapes[0]
        return self._shapes[0] + self._shapes[1:]

    def edges(self) -> ShapeList[Edge]:
        return ShapeList([
            e for shape in self._shapes for e in shape.edges()])

    def face(self):
        return make_face(self.wire())

    def tangent(self, shape_idx=-1, param=1):
        if self._shapes:
            return self._shapes[shape_idx].tangent_at(param)
        return self._start_tangent

    def normal(self, shape_idx=-1, param=1):
        if self._shapes:
            t = self._shapes[shape_idx].tangent_at(param)
        else:
            t = self._start_tangent
        return t.rotate(make_axis(self.plane), 90)

    def normal_loc(self, shape_idx=-1, param=1, tangent=1):
        p = self._shapes[shape_idx] @ param
        t = tangent * self.tangent(shape_idx, param)
        n = t.rotate(make_axis(self.plane), 90)
        return Location(Plane(p, x_dir=t, z_dir=n))

    def to_normal_plane(self, axis, start=None):
        if isinstance(axis, Pos):
            z_dir = getattr(axis, 'default_zdir', None)
            if z_dir is None:
                raise Exception('Position should have a default Z direction')
            return Plane(self.to_vector(axis, start), z_dir=self.to_direction(z_dir))
        else:
            gaxis = axis.located(self.plane.location)
            n = gaxis.direction.rotate(
                Axis(self.plane.origin, self.plane.z_dir), 90)
            return Plane(gaxis.position, z_dir=n)

    def add_shape(self, shape):
        self._shapes.append(shape)
        return shape

    def move(self, loc):
        if isinstance(loc, (tuple, Vector)):
            loc = Pos(loc)
        old = self._shapes
        self._shapes = [loc * it for it in self._shapes]

        for o, n in zip(old, self._shapes):
            if hasattr(o, '_lb_name'):
                self._named[o._lb_name] = n

    def __getitem__(self, idx):
        if idx in self._named:
            return self._named[idx]
        return self._shapes[idx]

    __getattr__ = __getitem__

    def revolvex(self):
        return revolve(self.face(), Axis.X.located(self.plane.location))

    def revolvey(self):
        return revolve(self.face(), Axis.Y.located(self.plane.location))

    def revolvez(self):
        return revolve(self.face(), Axis.Z.located(self.plane.location))

    def sweep(self, face):
        return sweep(Plane(self.s, z_dir=self.tangent(0, 0)) * face, self.wire())

    def extrude(self, amount, both=False, z_dir=True):
        dir = self.plane.z_dir if z_dir else None
        return extrude(self.face(), amount, both=both, dir=dir)

    def chains(self):
        if not self._shapes:
            return []

        rv = [c := [self._shapes[0]]]
        for s in self._shapes[1:]:
            if c[-1].e != s.s:
                c = [s]
                rv.append(c)
            else:
                c.append(s)

        return rv


class op_data_holder:
    def __init__(self, fn, name, reverse, connect, args, kwargs):
        self.fn = fn
        self.name = name
        self.reverse = reverse
        self.connect = connect
        self.args = args
        self.kwargs = kwargs


def build_line_op(fn):
    def inner(*args, **kwargs):
        name = kwargs.pop('name', None)
        reverse = kwargs.pop('reverse', False)
        connect = kwargs.pop('connect', False)
        fn(None, *args, **kwargs)
        return op_data_holder(fn, name, reverse, connect, args, kwargs)
    return inner


@build_line_op
def op_start(lb, start=None, tangent=None):
    if lb is None:
        return

    if start is not None:
        lb._start_point = lb.to_vector(start, lb.plane.origin)

    if tangent is not None:
        lb._start_tangent = lb.to_direction(tangent)


@build_line_op
def op_line(lb, length=None, angle=None, dir=None, start=None, to=None,
            until=None, tangent=None):
    if lb is None:
        assert _defined(to, length, until)
        return

    reset_tangent = False
    if start is None:
        start = lb.e
    else:
        reset_tangent = True
        start = lb.to_vector(start)

    if to is not None:
        return lb.add_shape(Line(start, lb.to_vector(to, start)))

    if dir is None:
        if tangent is None:
            if reset_tangent:
                tangent = lb.plane.x_dir
            else:
                tangent = lb.tangent()
        else:
            tangent = lb.to_direction(tangent)
        dir = tangent.rot(angle or 0, make_axis(lb.plane))
    else:
        dir = lb.to_direction(dir)

    if length is not None:
        return lb.add_shape(Line(start, start + dir * length))

    return lb.add_shape(_until_helper(lb, start, dir, until))


def _until_helper(lb, start, dir, until):
    if isinstance(until, Pos):
        until = lb.to_normal_plane(until, start)

    if isinstance(until, (Axis, Plane)):
        to = Axis(start, dir).intersect(until)
        return Line(start, to)

    return IntersectingLine(start, dir, until)


@build_line_op
def op_extend(lb, start=None, end=None):
    if lb is None:
        return

    l = lb._shapes.pop()
    segments = [l]
    if start is not None:
        if isinstance(start, (int, float)):
            nl = Line(l @ 0 - l.tangent_at(0) * start, l @ 0)
        else:
            nl = _until_helper(lb, l @ 0, l.tangent_at(0), start)
            nl.wrapped.Reverse()
        segments = [nl, *segments]

    if end is not None:
        if isinstance(end, (int, float)):
            nl = Line(l @ 1, l @ 1 + l.tangent_at(1) * end)
        else:
            nl = _until_helper(lb, l @ 1, l.tangent_at(1), end)
        segments = [*segments, nl]

    lb._shapes.extend(segments)
    return l


@build_line_op
def op_arc(lb, radius=None, size=None, to=None, tangent=True,
           short=True, center=None, start_angle=None, start=None):
    if lb is None:
        return

    if start is None:
        e = lb.e
    else:
        e = lb.to_vector(start)

    if tangent is True:
        tangent = lb.tangent()
    elif tangent is not None and tangent is not False:
        tangent = lb.to_direction(tangent)

    with lb._builder:
        if _defined_all(radius, size) and center is None:
            ax = make_axis(lb.plane)
            n = tangent.rotate(ax, math.copysign(90, size))
            c = e + n.normalized() * radius
            ep = c + (e - c).rotate(ax, size)
            return lb.add_shape(BaseLineObject(Edge.make_tangent_arc(e, tangent, ep)))
        elif _defined(to) and tangent:
            return lb.add_shape(TangentArc(e, lb.to_vector(to), tangent=tangent))
        elif _defined_all(to, radius) and not tangent:
            return lb.add_shape(RadiusArc(e, lb.to_vector(to), radius, short_sagitta=short))
        elif _defined_all(center, radius):
            start_angle = start_angle or 0
            if center is True:
                center = lb.e
            else:
                center = lb.to_vector(center)
            return lb.add_shape(CenterArc(center, radius, start_angle, size))
    assert False


@build_line_op
def op_ellipse_arc(lb, r1, r2, start, end):
    if lb is None:
        return

    edge = Edge.make_ellipse(r1, r2, lb.plane, start, end)
    s = BaseLineObject(edge)
    return lb.add_shape(Pos(lb.e - s @ 0) * s)


@build_line_op
def op_drop(lb, idx=0):
    if not lb:
        return

    lb._shapes.pop(idx)


@build_line_op
def op_close(lb, both=None, end=None, start=None, mirror=None):
    if not lb:
        return

    if both:
        start = end = both

    if mirror is not None:
        start = end = mirror

    if isinstance(start, (Axis, Pos)):
        start = lb.to_normal_plane(start)

    if isinstance(end, (Axis, Pos)):
        end = lb.to_normal_plane(end)

    if end is not None:
        p = lb.e.project_to_plane(end)
        if p not in (lb.e, lb.s):
            lb.add_shape(Line(lb.e, p))

    if start is not None:
        p = lb.s.project_to_plane(start)
        if p not in (lb.e, lb.s):
            lb._shapes = [Line(p, lb.s), *lb._shapes]

    if mirror is not None:
        return lb.add_shape(b123_mirror(lb.wire(), start))

    return lb.add_shape(Line(lb.e, lb.s))


@build_line_op
def op_trim(lb, point, near_by=None, add=False):
    if not lb:
        return
    s = lb._shapes[-1]
    other = None
    if isinstance(point, by_tangent):
        rv, other = point.trim(lb)
    else:
        if isinstance(point, Axis):
            ax = point.located(lb.plane.location)
            point = intersection(s, ax, near_by=near_by)
            other = Line(point, ax.position)
        param = param_on_point(s, point)
        rv = lb._shapes[-1] = trim_wire(s, end=param)

    if other is not None and add:
        lb.add_shape(other)

    return rv


@build_line_op
def op_move(lb, start=None, end=None):
    if not lb:
        return

    targets = lb.chains()[-1]
    if start is not None:
        start = lb.to_vector(start)
        pos = Pos(start - targets[0].s)
    elif end is not None:
        end = lb.to_vector(end)
        pos = Pos(end - targets[-1].e)

    for it in targets:
        it.move(pos)


class by_tangent:
    def __init__(self, obj, sort_by=Axis.Y, idx=-1):
        self.obj = obj
        self.sort_by = sort_by
        self.idx = idx

    def trim(self, lb):
        s = lb._shapes[-1]
        cl = Line(s.edge().arc_center, self.point)
        cc = Pos(cl @ 0.5) * Edge.make_circle(cl.length/2)
        ip = intersection(s, cc, sort_by=self.sort_by, idx=self.idx)
        param = param_on_point(s, ip)
        rv = lb._shapes[-1] = trim_wire(s, end=param)
        return rv, Line(rv @ 1, lb.to_vector(self.obj))


@build_line_op
def op_fillet(lb, radius, count=1):
    if not lb:
        return
    fpoints = [lb._shapes[-i-1] @ 0 for i in range(count)]
    sidx = len(lb._shapes) - 1 - count
    spoint = lb._shapes[sidx] @ 0
    fused = lb._shapes[sidx].fuse(*lb._shapes[sidx+1:])
    w = Wire(fused.edges())
    fobj = fillet([v for v in w.vertices() if Vector(v) in fpoints], radius)
    if fobj @ 0 != spoint:
        fobj.wrapped.Reverse()
    lb._shapes[sidx:] = [fobj]
    return fobj


@build_line_op
def op_chamfer(lb, length, count=1, length2=None, angle=None):
    if not lb:
        return
    fpoints = [lb._shapes[-i-1] @ 0 for i in range(count)]
    sidx = len(lb._shapes) - 1 - count
    spoint = lb._shapes[sidx] @ 0
    fused = lb._shapes[sidx].fuse(*lb._shapes[sidx+1:])
    w = Wire(fused.edges())
    fobj = chamfer([v for v in w.vertices() if Vector(v) in fpoints], length=length, length2=length2, angle=angle)
    if fobj @ 0 != spoint:
        fobj.wrapped.Reverse()
    lb._shapes[sidx:] = [fobj]
    return fobj
