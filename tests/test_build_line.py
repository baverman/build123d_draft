import io
import pytest
from pytest import approx

from build123d import *
from build123d_draft import *


def test_op_close_axis_transformation():
    l = build_line(Plane.XZ.offset(-5)).append(
        X(10), Y(10), op_close(Axis.Y)
    )
    v = [Vector(it) for it in l.wire().vertices()]
    assert v == [Vector(it) for it in [(0, 5, 0), (10, 5, 0), (10, 5, 10), (0, 5, 10)]]


def test_localize_direction_vector():
    l = build_line(Plane.XZ.offset(-5))
    assert l.to_direction((0, 1)) == Vector(0, 0, 1)
    assert l.to_direction(Vector(0, 1)) == Vector(0, 1, 0)
    assert l.to_direction(Axis.Y) == Vector(0, 0, 1)
    assert l.to_direction(Pos(0, 1)) == Vector(0, 0, 1)


def assert_cont_edges(edges, *points):
    epoints = [(it.s, it.e) for it in edges]
    points = list(zip(points, points[1:]))
    assert epoints == points


def test_trim():
    l = build_line().append(
        op_line(start=XX(10), to=XX(5)),
        op_line(to=XX(0))
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
