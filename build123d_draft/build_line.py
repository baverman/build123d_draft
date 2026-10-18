import math
import functools
from itertools import chain as it_chain
from dataclasses import dataclass, replace
from typing import (
    Any,
    TypeAlias,
    Mapping,
    Callable,
    ParamSpec,
    Concatenate,
    Literal,
    Iterator,
    TypeGuard,
    assert_type,
)

from build123d import BuildLine, Sketch, Part
from build123d.geometry import Plane, Axis, Pos, Vector, Location, VectorLike
from build123d.topology import Shape, ShapeList, Wire, Edge, Vertex
from build123d.topology.shape_core import TOPODS
from build123d.topology.one_d import Mixin1D
from build123d.topology.composite import Curve
from build123d.objects_curve import (
    Line,
    IntersectingLine,
    TangentArc,
    RadiusArc,
    CenterArc,
    BaseEdgeObject,
)
from build123d.operations_sketch import make_face
from build123d.operations_generic import mirror as b123_mirror, sweep, fillet, chamfer, SweepType
from build123d.operations_part import extrude, revolve
from build123d.build_enums import AngularDirection

from .utils import (
    _defined,
    _defined_all,
    assert_args,
    debug,
)
from .tools import make_axis, intersection, PPos, param_on_point, trim_wire, reversed_wire

__all__ = [
    'Angle',
    'build_line',
    'build_line_op',
    'Dir',
    'Op',
    'op_arc',
    'op_chamfer',
    'op_close',
    'op_drop',
    'op_ellipse_arc',
    'op_extend',
    'op_fillet',
    'op_line',
    'op_move',
    'op_start',
    'op_trim',
    'PDir',
    'TrimOp',
]

_P = ParamSpec('_P')
VLike = Vector | Pos | PPos | Axis | tuple[float, ...]
TLike = Vector | Pos | Axis | tuple[float, ...]
BuildLineOp: TypeAlias = Vector | Pos | tuple[float, ...] | Shape[Any] | 'Op'
UntilType = Curve | Edge | Wire | Axis | Plane | Pos


def is_vlike(obj: object) -> TypeGuard[VLike]:
    return isinstance(obj, (Vector, Pos, PPos, Axis, tuple))


def is_point_like(obj: object) -> TypeGuard[Vector | tuple[float, ...]]:
    return isinstance(obj, (Vector, tuple))


class TrimOp:
    def trim(self, lb: build_line) -> tuple[Mixin1D[Any], Mixin1D[Any]]: ...  # type: ignore[empty-body]


class build_line:
    def __init__(
        self,
        start: Plane | VLike | None = None,
        plane: Plane = Plane.XY,
        tangent: TLike | None = None,
    ) -> None:
        # TODO: use context to get current plane
        if isinstance(start, Plane):
            nstart, plane = None, start
        else:
            nstart = start

        self.plane = plane
        self._shapes: list[Mixin1D[Any]] = []
        self._named: dict[str, Mixin1D[Any]] = {}
        if nstart is None:
            self._start_point = plane.origin
        else:
            self._start_point = self.to_vector(nstart, plane.origin)

        if tangent is None:
            self._start_tangent = plane.x_dir
        else:
            self._start_tangent = self.to_direction(tangent)

        self._builder = BuildLine(plane)

    def to_local_vector(self, v: Vector) -> Vector:
        return v.transform(self.plane.forward_transform)

    def to_vector(self, v: VLike, ref: Vector | None = None) -> Vector:
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

    def to_direction(self, v: TLike) -> Vector:
        nv: Vector | Axis | tuple[float, ...]
        if isinstance(v, Pos):
            nv = tuple(v.position)
        else:
            nv = v

        if isinstance(nv, Vector):
            return nv
        elif isinstance(nv, Axis):
            ax: Axis = nv.located(self.plane.location)
            return ax.direction
        elif isinstance(nv, tuple):
            origin = self.to_vector((0, 0, 0))
            return self.to_vector(nv) - origin

        assert False, f'Unsupported type {type(nv)}'

    def apply(self, op: BuildLineOp) -> None:
        if isinstance(op, (Vector, Pos, tuple)):
            cop: Vector | Pos | tuple[float, ...] = op
            self._shapes.append(Line(self.e, self.to_vector(cop)))
        elif isinstance(op, Shape):
            self._shapes.append(op)
        else:
            s = op(self)
            if op.name and s is not None:
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

    def append(self, *ops: BuildLineOp) -> 'build_line':
        for idx, op in enumerate(ops):
            try:
                self.apply(op)
            except Exception as e:
                raise Exception(f'Error applying {op}#{idx}: {e}') from e
        return self

    @property
    def e(self) -> Vector:
        if self._shapes:
            return self._shapes[-1] @ 1
        else:
            return self._start_point

    @property
    def s(self) -> Vector:
        return self._shapes[0] @ 0

    @property
    def ss(self) -> Vector:
        return self._shapes[0] @ 1

    @property
    def ee(self) -> Vector:
        return self._shapes[-1] @ 0

    def wire(self) -> Wire:
        if len(self._shapes) == 1:
            return self._shapes[0]
        return self._shapes[0] + self._shapes[1:]

    def edges(self) -> ShapeList[Edge]:
        return ShapeList([e for shape in self._shapes for e in shape.edges()])

    def face(self) -> Sketch:
        return make_face(self.wire())

    def tangent(self, shape_idx: int = -1, param: float = 1) -> Vector:
        if self._shapes:
            return self._shapes[shape_idx].tangent_at(param)
        return self._start_tangent

    def normal(self, shape_idx: int = -1, param: float = 1) -> Vector:
        if self._shapes:
            t = self._shapes[shape_idx].tangent_at(param)
        else:
            t = self._start_tangent
        return t.rotate(make_axis(self.plane), 90)

    def normal_loc(self, shape_idx: int = -1, param: float = 1, tangent: float = 1) -> Location:
        p = self._shapes[shape_idx] @ param
        t = tangent * self.tangent(shape_idx, param)
        n = t.rotate(make_axis(self.plane), 90)
        return Location(Plane(p, x_dir=t, z_dir=n))

    def to_normal_plane(self, axis: Pos | Axis, start: Vector | None = None) -> Plane:
        if isinstance(axis, Pos):
            z_dir = getattr(axis, 'default_zdir', None)
            if z_dir is None:
                raise Exception('Position should have a default Z direction')
            return Plane(self.to_vector(axis, start), z_dir=self.to_direction(z_dir))
        else:
            gaxis: Axis = axis.located(self.plane.location)
            n = gaxis.direction.rotate(Axis(self.plane.origin, self.plane.z_dir), 90)
            return Plane(gaxis.position, z_dir=n)

    def add_shape(self, shape: Shape[TOPODS]) -> Shape[TOPODS]:
        self._shapes.append(shape)
        return shape

    def move(self, loc: Vector | Location | tuple[float, ...]) -> None:
        if isinstance(loc, (tuple, Vector)):
            loc = Pos(loc)
        old = self._shapes
        self._shapes = [loc * it for it in self._shapes]

        for o, n in zip(old, self._shapes):
            if hasattr(o, '_lb_name'):
                self._named[o._lb_name] = n

    def __getitem__(self, idx: int) -> Mixin1D[Any]:
        return self._shapes[idx]

    def __iter__(self) -> Iterator[Mixin1D[Any]]:
        return iter(self._shapes)

    def __getattr__(self, name: str) -> Mixin1D[Any]:
        try:
            return self._named[name]
        except KeyError:
            raise AttributeError(name)

    def revolvex(self) -> Part:
        return revolve(self.face(), Axis.X.located(self.plane.location))

    def revolvey(self) -> Part:
        return revolve(self.face(), Axis.Y.located(self.plane.location))

    def revolvez(self) -> Part:
        return revolve(self.face(), Axis.Z.located(self.plane.location))

    def sweep(self, face: SweepType) -> Part:
        return sweep(Plane(self.s, z_dir=self.tangent(0, 0)) * face, self.wire())

    def extrude(self, amount: float, both: bool = False, z_dir: bool = True) -> Part:
        dir = self.plane.z_dir if z_dir else None
        return extrude(self.face(), amount, both=both, dir=dir)

    def chains(self) -> list[list[Shape[Any]]]:
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


@dataclass
class Op:
    fn: Callable[..., Mixin1D[Any] | None]
    name: str
    reverse: bool
    connect: bool
    args: tuple[Any, ...]
    kwargs: Mapping[str, Any]

    def __call__(self, lb: build_line) -> Mixin1D[Any] | None:
        return self.fn(lb, *self.args, **self.kwargs)

    def __repr__(self) -> str:
        params: list[str] = []
        params.extend(repr(it) for it in self.args)
        params.extend(f'{k}={v!r}' for k, v in self.kwargs.items())
        return f'{self.fn.__name__}({", ".join(params)})'

    def named(self, name: str) -> Op:
        return replace(self, name=name)

    @property
    def connected(self) -> Op:
        return replace(self, connect=True)

    @property
    def reversed(self) -> Op:
        return replace(self, reverse=True)


def build_line_op(
    fn: Callable[Concatenate[build_line | None, _P], Mixin1D[Any] | None],
) -> Callable[_P, Op]:
    @functools.wraps(fn)
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> Op:
        name: str = kwargs.pop('name', None)  # type: ignore[assignment]
        reverse: bool = kwargs.pop('reverse', False)  # type: ignore[assignment]
        connect: bool = kwargs.pop('connect', False)  # type: ignore[assignment]
        fn(None, *args, **kwargs)
        return Op(fn, name, reverse, connect, args, kwargs)

    return inner


@build_line_op
def op_start(
    lb: build_line | None, start: VLike | None = None, tangent: TLike | None = None
) -> None:
    if lb is None:
        return

    if start is not None:
        lb._start_point = lb.to_vector(start, lb.plane.origin)

    if tangent is not None:
        lb._start_tangent = lb.to_direction(tangent)


@dataclass
class Angle:
    angle: float


class Dir:
    direction: TLike

    def __init__(self, X: float | TLike = 0, Y: float = 0, Z: float = 0, angle: float = 0) -> None:
        self.angle = angle
        if isinstance(X, (float, int)):
            self.direction = Vector(X, Y, Z)
        else:
            self.direction = X

    def localize(self, lb: build_line) -> Vector:
        tangent = lb.to_direction(self.direction)
        if self.angle != 0:
            return tangent.rotate(make_axis(lb.plane), self.angle)
        return tangent


class PDir:
    position: VLike
    direction: Dir

    def __init__(self, position: VLike, direction: TLike | None = None, angle: float = 0) -> None:
        self.position = position
        self.direction = Dir(direction or (1, 0, 0), angle=angle)


def _parse_start(
    lb: build_line,
    start: VLike | Dir | PDir | Angle | None = None,
) -> tuple[Vector, Vector | None]:
    if start is None:
        return lb.e, lb.tangent()

    if isinstance(start, Dir):
        return lb.e, start.localize(lb)
    elif isinstance(start, PDir):
        return lb.to_vector(start.position), start.direction.localize(lb)
    elif isinstance(start, Angle):
        return lb.e, lb.tangent().rotate(make_axis(lb.plane), start.angle)

    return lb.to_vector(start), lb.to_direction((1, 0, 0))


@build_line_op
def op_line(
    lb: build_line | None,
    end: float | VLike | UntilType,
    start: VLike | Dir | PDir | Angle | None = None,
) -> Mixin1D[Any] | None:
    if lb is None:
        return None

    nstart, tangent = _parse_start(lb, start)
    assert tangent

    if isinstance(end, (float, int)):
        return lb.add_shape(Line(nstart, nstart + tangent.normalized() * end))

    if is_point_like(end):
        return lb.add_shape(Line(nstart, lb.to_vector(end, nstart)))

    nend: UntilType = end  # type: ignore[assignment]
    return lb.add_shape(_until_helper(lb, nstart, tangent, nend))


def _until_helper(lb: build_line, start: Vector, dir: Vector, until: UntilType) -> BaseEdgeObject:
    nuntil: Curve | Edge | Wire | Axis | Plane
    if isinstance(until, Pos):
        nuntil = lb.to_normal_plane(until, start)
    else:
        nuntil = until

    if isinstance(nuntil, (Axis, Plane)):
        # TODO: intersection could be parallel and none
        to: Vector = Axis(start, dir).intersect(nuntil)  # type: ignore[assignment]
        return Line(start, to)

    return IntersectingLine(start, dir, nuntil)


@build_line_op
def op_extend(
    lb: build_line | None,
    start: float | UntilType | None = None,
    end: float | UntilType | None = None,
) -> Mixin1D[Any] | None:
    if lb is None:
        return None

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
def op_arc(
    lb: build_line | None,
    radius: float | None = None,
    size: float | None = None,
    to: VLike | None = None,
    tangent: TLike | bool = True,
    short: bool = True,
    center: VLike | None = None,
    start_angle: float | None = None,
    start: VLike | None = None,
) -> Mixin1D[Any] | None:
    if lb is None:
        assert_args(
            locals(),
            ['radius', 'size', '+tangent', '-center', '-to'],
            ['to', '+tangent', '-center', '-radius', '-size'],
            ['to', 'radius', '!tangent', '-center'],
            ['center', 'radius', 'size', (None, 'start_angle'), '-to'],
        )
        return None

    if start is None:
        e = lb.e
    else:
        e = lb.to_vector(start)

    if tangent is True:
        tangent = lb.tangent()
    elif tangent is not None and tangent is not False:
        tangent = lb.to_direction(tangent)

    if _defined_all(radius, size) and center is None:
        # JernArc, reimplemented
        ax = make_axis(lb.plane)
        n = tangent.rotate(ax, math.copysign(90, size))  # type: ignore[union-attr,arg-type]
        c = e + n.normalized() * radius  # type: ignore[operator]
        ep = c + (e - c).rotate(ax, size)  # type: ignore[arg-type,operator]
        return lb.add_shape(BaseEdgeObject(Edge.make_tangent_arc(e, tangent, ep)))  # type: ignore[arg-type]
    elif _defined(to) and tangent:
        with lb._builder:
            TangentArc(
                lb.to_local_vector(e),
                lb.to_local_vector(lb.to_vector(to, e)),  # type: ignore[arg-type]
                tangent=lb.to_local_vector(tangent),
            )
        return lb.add_shape(BaseEdgeObject(lb._builder.line.edges()[0]))  # type: ignore[union-attr]
    elif _defined_all(to, radius) and not tangent:
        with lb._builder:
            RadiusArc(
                lb.to_local_vector(e),
                lb.to_local_vector(lb.to_vector(to, e)),  # type: ignore[arg-type]
                radius,  # type: ignore[arg-type]
                short_sagitta=short,
            )
        return lb.add_shape(BaseEdgeObject(lb._builder.line.edges()[0]))  # type: ignore[union-attr]
    elif _defined_all(center, radius, size):
        start_angle = start_angle or 0
        if center is True:  # type: ignore[comparison-overlap]
            center = lb.e
        else:
            center = lb.to_vector(center, e)  # type: ignore[arg-type]
        with lb._builder:
            CenterArc(lb.to_local_vector(center), radius, start_angle, size)  # type: ignore[arg-type]
        return lb.add_shape(BaseEdgeObject(lb._builder.line.edges()[0]))  # type: ignore[union-attr]

    assert False


@build_line_op
def op_ellipse_arc(
    lb: build_line | None,
    r1: float,
    r2: float,
    size: float,
    start_angle: float = 0,
    start: VLike | None = None,
    tangent: TLike | Literal[True] = True,
) -> Mixin1D[Any] | None:
    if lb is None:
        return None

    if start is None:
        e = lb.e
    else:
        e = lb.to_vector(start)

    if tangent is True:
        et = lb.tangent()
    else:
        et = lb.to_direction(tangent)

    edge = Edge.make_ellipse(r1, r2, lb.plane, start_angle, start_angle + size)
    s = BaseEdgeObject(edge)

    ra = (s % 0).get_signed_angle(et, lb.plane.z_dir)
    s = s.rotate(Axis(s @ 0, lb.plane.z_dir), ra)
    return lb.add_shape(Pos(e - s @ 0) * s)


@build_line_op
def op_drop(lb: build_line | None, idx: int = 0) -> None:
    if not lb:
        return

    lb._shapes.pop(idx)


@build_line_op
def op_close(
    lb: build_line | None,
    both: Pos | Axis | Plane | None = None,
    end: Pos | Axis | Plane | None = None,
    start: Pos | Axis | Plane | None = None,
    mirror: Pos | Axis | Plane | None = None,
) -> Mixin1D[Any] | None:
    if not lb:
        return None

    if both:
        start = end = both

    if mirror is not None:
        start = end = mirror

    nstart: Plane | None
    if isinstance(start, (Axis, Pos)):
        nstart = lb.to_normal_plane(start)
    else:
        nstart = start

    nend: Plane | None
    if isinstance(end, (Axis, Pos)):
        nend = lb.to_normal_plane(end)
    else:
        nend = end

    if nend is not None:
        p = lb.e.project_to_plane(nend)
        if p not in (lb.e, lb.s):
            lb.add_shape(Line(lb.e, p))

    if nstart is not None:
        p = lb.s.project_to_plane(nstart)
        if p not in (lb.e, lb.s):
            lb._shapes = [Line(p, lb.s), *lb._shapes]

    if mirror is not None:
        assert nstart
        return lb.add_shape(b123_mirror(lb.wire(), nstart))

    return lb.add_shape(Line(lb.e, lb.s))


@build_line_op
def op_trim(
    lb: build_line | None,
    point: TrimOp | Axis | Vector,
    near_by: Vector | Shape[Any] | None = None,
    add: bool = False,
) -> Mixin1D[Any] | None:
    if not lb:
        return None
    s = lb._shapes[-1]
    other = None
    if isinstance(point, TrimOp):
        rv, other = point.trim(lb)
    else:
        if isinstance(point, Axis):
            ax: Axis = point.located(lb.plane.location)
            npoint = intersection(s, ax, near_by=near_by)
            other = Line(npoint, ax.position)
        param = param_on_point(s, npoint)
        assert param
        rv = lb._shapes[-1] = trim_wire(s, end=param)

    if other is not None and add:
        lb.add_shape(other)

    return rv


@build_line_op
def op_move(
    lb: build_line | None, start: VLike | None = None, end: VLike | None = None
) -> Mixin1D[Any] | None:
    if not lb:
        return None

    targets = lb.chains()[-1]
    if start is not None:
        start = lb.to_vector(start)
        pos = Pos(start - targets[0].s)
    elif end is not None:
        end = lb.to_vector(end)
        pos = Pos(end - targets[-1].e)

    for it in targets:
        it.move(pos)

    return None


def _fillet_helper(
    lb: build_line, count: int, closed: bool
) -> tuple[int, list[Vertex], list[Wire]]:
    l = len(lb._shapes)
    if closed:
        assert count <= l, f'vertex count should be less or equal than number of shapes'
    else:
        assert count < l, f'vertex count should be less than number of shapes'

    if closed:
        sidx = l - count
        xs = [*range(sidx, l), 0]
        keep = lb._shapes[1:sidx]
    else:
        sidx = l - 1 - count
        xs = list(range(sidx, l))
        keep = lb._shapes[:sidx]

    to_fuse = [lb._shapes[i] for i in xs]
    fpoints = [it.at(1) for it in to_fuse[:-1]]
    fused = to_fuse[0].fuse(*to_fuse[1:])
    w = Wire(fused.edges())
    # from .testing import sadd
    # sadd(boo=w)
    vlist = [v for v in w.vertices() if Vector(v) in fpoints]
    return sidx, vlist, keep


@build_line_op
def op_fillet(
    lb: build_line | None, radius: float, count: int = 1, closed: bool = False
) -> Mixin1D[Any] | None:
    if not lb:
        return None
    sidx, vlist, keep = _fillet_helper(lb, count, closed)
    spoint = lb._shapes[sidx] @ 0
    fobj = fillet(vlist, radius)
    if not closed and fobj @ 0 != spoint:
        fobj = reversed_wire(fobj)
        # fobj.wrapped.Reverse()
    keep.append(fobj)
    lb._shapes = keep
    return fobj


@build_line_op
def op_chamfer(
    lb: build_line | None,
    length: float,
    count: int = 1,
    length2: float | None = None,
    angle: float | None = None,
    closed: bool = False,
) -> Mixin1D[Any] | None:
    if not lb:
        return None
    sidx, vlist, keep = _fillet_helper(lb, count, closed)
    spoint = lb._shapes[sidx] @ 0
    fobj = chamfer(vlist, length=length, length2=length2, angle=angle)
    if fobj @ 0 != spoint:
        fobj = reversed_wire(fobj)
        # fobj.wrapped.Reverse()
    keep.append(fobj)
    lb._shapes = keep
    return fobj
