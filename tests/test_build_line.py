import io
import pytest
from typing import Any
from pytest import approx

from build123d import *
from build123d.topology import Shape
from build123d_draft import *  # type: ignore[assignment]


def test_op_close_axis_transformation() -> None:
    l = build_line(Plane.XZ.offset(-5)).append(
        X(10), Y(10), op_close(Axis.Y)
    )
    v = [Vector(it) for it in l.wire().vertices()]
    v = [l.s]
    for it in l:
        v.append(it.e)
    assert v == [Vector(it) for it in [(0, 5, 0), (10, 5, 0), (10, 5, 10), (0, 5, 10), (0, 5, 0)]]


def test_localize_direction_vector() -> None:
    l = build_line(Plane.XZ.offset(-5))
    assert l.to_direction((0, 1)) == Vector(0, 0, 1)
    assert l.to_direction(Vector(0, 1)) == Vector(0, 1, 0)
    assert l.to_direction(Axis.Y) == Vector(0, 0, 1)
    assert l.to_direction(Pos(0, 1)) == Vector(0, 0, 1)


def assert_cont_edges(edges: list[Edge], *points: Vector) -> None:
    epoints = [(it.s, it.e) for it in edges]
    npoints = list(zip(points, points[1:]))
    assert epoints == npoints


def test_trim() -> None:
    l = build_line().append(
        op_line(start=XX(10), end=XX(5)),
        op_line(end=XX(0))
    )

    # direct wire
    w = Wire(l.edges())
    p = param_on_point(w, Vector(8))
    assert p == 0.2

    nw = trim_wire(w, end=p)
    assert nw.s == Vector(10)
    assert nw.e == Vector(8)
    assert_cont_edges(nw.edges(), Vector(10), Vector(8))

    # reversed edges
    w = reversed_wire(w)
    p = param_on_point(w, Vector(8))
    assert p == 0.8

    nw = trim_wire(w, end=p)
    assert nw.s == Vector(0)
    assert nw.e == Vector(8)
    assert_cont_edges(nw.edges(), Vector(0), Vector(5), Vector(8))

    # reversed wire
    w = Wire(l.edges())
    w.wrapped.Reverse()
    p = param_on_point(w, Vector(8))
    assert p == 0.8

    nw = trim_wire(w, end=p)
    assert nw.s == Vector(0)
    assert nw.e == Vector(8)


def assert_bb(shape: Shape[Any], min: VectorLike, max: VectorLike) -> None:
    bb = shape.bounding_box()
    assert (bb.min, bb.max) == (Vector(min), Vector(max))


def test_radius_arc() -> None:
    l = build_line(Plane.XZ).append(op_arc(start=At(None, FREE), end=(30, 0), d=50))
    assert_bb(l.wire(), (0, 0, 0), (30, 0, 5))

    l = build_line(Plane.XZ).append(op_arc(start=At(None, FREE), end=(30, 0), d=-50))
    assert_bb(l.wire(), (0, 0, -5), (30, 0, 0))

    l = build_line(Plane.XZ).append(op_arc(start=At(None, FREE), end=(30, 0), d=50, short=False))
    assert_bb(l.wire(), (-10, 0, -45), (40, 0, 0))


def test_jern_arc() -> None:
    l = build_line(Plane.XZ).append(op_arc(180, r=20))
    assert_bb(l.wire(), (0, 0, 0), (20, 0, 40))

    l = build_line(Plane.XZ).append(op_arc(-90, r=20))
    assert_bb(l.wire(), (0, 0, -20), (20, 0, 0))

    l = build_line(Plane.XZ).append(op_arc((20, 20)))
    assert_bb(l.wire(), (0, 0, 0), (20, 0, 20))
