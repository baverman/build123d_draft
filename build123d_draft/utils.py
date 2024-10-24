import sys
import OCP
from OCP.BRep import BRep_Tool
from build123d.geometry import Vector, Pos
from build123d.topology import isclose_b, Wire, Edge
from build123d.build_common import Builder


def reversed_wire(wire):
    elist = []
    for e in wire.edges():
        elist.append(e.reversed())
    return Wire(reversed(elist))


def edge_curve(edge):
    p1, p2 = BRep_Tool.Range_s(edge.wrapped)
    c = BRep_Tool.Curve_s(edge.wrapped, p1, p2)
    return c, (p1, p2)


def param_on_point(wire, point, normalized=True):
    is_reversed = wire.wrapped.Orientation() == OCP.TopAbs.TopAbs_Orientation.TopAbs_REVERSED
    edges = wire.edges()
    si = 0
    if is_reversed:
        edges = reversed(edges)
        si = 1

    U = 0
    candidates = []
    pt = Vector(point).to_pnt()
    for e in edges:
        c, pr = edge_curve(e)
        poc = OCP.GeomAPI.GeomAPI_ProjectPointOnCurve(pt, c)
        p = poc.LowerDistanceParameter()
        if pr[0] <= p <= pr[1]:
            candidates.append((poc.LowerDistance(), U + abs(pr[si] - p)))
        U += abs(pr[0] - pr[1])

    if not candidates:
        return None

    candidates.sort()
    u = candidates[0][1]
    if normalized:
        return u / U
    return u


def trim_wire(wire, start=0, end=1):
    is_reversed = wire.wrapped.Orientation() == OCP.TopAbs.TopAbs_Orientation.TopAbs_REVERSED

    edges = wire.edges()
    if is_reversed:
        edges.reverse()

    curves = [(it, edge_curve(it)) for it in edges]
    U = sum(abs(pr[0] - pr[1]) for _, (_, pr) in curves)
    start *= U
    end *= U

    nedges = []
    u2 = 0
    for e, (c, pr) in curves:
        u1 = u2
        u2 = (u1 + abs(pr[0] - pr[1]))
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

    assert nedges

    if is_reversed:
        nedges.reverse()

    rv = Wire([Edge(it) for it in nedges])

    if is_reversed:
        rv.wrapped.Reverse()

    return rv


class FakeBuilder(Builder):
    def _add_to_pending(self, *objects, face_plane = None):
        return NotImplementedError  # pragma: no cover

    @property
    def _obj(self):
        raise NotImplementedError  # pragma: no cover

    def validate_inputs(self, validating_class, objects = None):
        pass


def _defined(*args):
    return any(it is not None for it in args)


def _defined_all(*args):
    return all(it is not None for it in args)


def _iter_args(col):
    for it in col:
        if type(it) is str:
            yield it.lstrip('+-!')
        elif it is None:
            pass
        else:
            yield from _iter_args(it)


def _eval_args(vals, case):
    tcase = type(case)
    if tcase is str:
        if case[0] == '+':
            v = vals[case[1:]]
            return v is not False and v is not None
        elif case[0] == '!':
            return vals[case[1:]] is False
        elif case[0] == '-':
            return vals[case[1:]] is None
        return vals[case] is not None
    elif tcase is list:
        return all(_eval_args(vals, it) for it in case)
    elif tcase is tuple:
        mc = sum(_eval_args(vals, it) for it in case)
        if case[0] is None:
            return mc <= 1
        return mc == 1
    elif case is None:
        return False
    return False


def assert_args(vals, *cases):
    matched_count = sum(_eval_args(vals, it) for it in cases)
    if matched_count == 1:
        return

    assert False, f'matched_cases={matched_count}: ' + str(cases)


class PPos(Pos):
    def __init__(self, X=None, Y=None, Z=None):
        self._initial = (X, Y, Z)

    def combine_abs(self, v):
        if v is None:
            v = Vector(0, 0, 0)

        r = [0, 0, 0]
        for idx, (iv, vv) in enumerate(zip(self._initial, v.to_tuple())):
            r[idx] = iv if iv is not None else vv

        return Vector(*r)


def debug(*args, **kwargs):
    kwargs['file'] = sys.stderr
    return print(*args, **kwargs)
