# repl-client
"""
## TTT Build123d tutorials

This is a reimplementation of [Too Tall Toby tutorials][tttt] documenation
section using `build_line` as a main draft tool.

[tttt]: https://build123d.readthedocs.io/en/latest/tttt.html
"""
from build123d import *
from build123d_draft import *
from pytest import approx
import pytest

from tests.conftest import view
from build123d_draft.testing import *

densa = 1020e-6
densb = 2700e-6
densc = 7800e-6

@slist
@pytest.mark.views((100, 0))
def test_ppack_01_01():
    l = build_line(Plane.XZ.offset(25)).append(
        Y(42),
        op_arc(26, -180, name='a'),
        YY(15),
        X(30),
        op_fillet(9),
        op_close(Axis.X),
    )

    hole = cbore_d(34, 4, 24, 12)
    part = mirror_add(l.extrude(-12) - Pos(l.a.arc_center) * -R.Y * hole)

    part += Box(115, 50, 15, align=A.dw)
    part -= X(115-10) * make_slot(90, h=15, center=False, d=12, align=A.e)

    tl = build_line(X(9), Plane.YZ).append(
        op_line(angle=60, until=Y(8)), op_close(mirror=Axis.Y)
    )
    part -= tl.extrude(115)

    part &= extrude(RectangleRounded(115, 50, 6, align=A.w), 100)
    assert part.volume*densc == approx(797.14, abs=0.01)
    return part


@slist
@pytest.mark.views((60, 15), view(60, 15, clip=-Plane.XZ), size=(480, 480))
def test_ppack_01_02():
    l = build_line(X(49/2), Plane.XZ).append(
        Y(40),
        op_ellipse_arc(20, 8, 90),
        op_close(Axis.Y)
    )
    base = l.revolvey()

    hl = build_line(Plane.XZ).append(
        op_arc(17, 180, center=(-15, 20), start_angle=90))
    handle = hl.sweep(Ellipse(2, 5))

    _, edges = new_edges_add(handle, base)
    part = fillet(edges, 1)

    il = build_line(X(42/2), Plane.XZ).append(
        op_line(angle=94, until=Y(37)),
        XX(0),
        op_fillet(3),
        op_close(Axis.Y)
    )
    part -= il.revolvey()

    assert part.volume*densa == approx(43.09, abs=0.01)
    return part


@slist
@pytest.mark.views((90, 0))
def test_ppack_01_03():
    l = build_line(Plane.XZ).append(
        Y(-34), X(95), Y(34), op_fillet(18, 2),
        X(-18), Y(16-34), XX(14), YY(0), op_fillet(7, 2), op_close()
    )
    part = l.extrude(8, both=True)

    loc1 = X(14-23) * -R.X
    part += loc1 * Cylinder(23, r=8, align=A.u)
    part -= loc1 * CounterSinkHole(5.5/2, 11.2/2, 23, 90)

    c2 = X(95-18) * -R.X * Cylinder(18, r=8, align=A.u)
    part = part + c2 - c2.new(d=5.5)

    assert part.volume*densb == approx(96.13, abs=0.01)
    return part


@slist
def test_ppack_01_04():
    l = build_line(Plane.XZ).append(
        X(80-38/2-10), Y(7-30), op_fillet(5),
        X(10), Y(30), XX(0), op_fillet(10), op_close()
    )
    base = l.extrude(30, both=True)

    c1 = Cylinder(7+21-8, d=38, align=A.d)

    _, edges = new_edges_add(c1, base)
    part = fillet(edges.filter_by(Plane.XY), 4)
    part &= X(-38/2) * Box(80+38, 38, 100, align=A.w)

    c2 = Pos(Z=21+7) * Cylinder(8, d=26, align=A.u)
    part = part + c2 - c2.new(21+7, d=16)

    sloc = Pos(80-38/2, Z=7-30) * R.X
    part -= sloc * make_slot((17-9)*2, h=-5, r=9)
    part -= sloc * make_slot((17-9)*2, h=-10, r=6)

    assert part.volume*densc == approx(310, abs=0.01)
    return part


@slist
def test_ppack_01_06():
    l = build_line((44/2, 69-15)).append(
        op_arc(10, -45-90, name='a'),
        op_line(until=XX(15)), YY(0), op_fillet(12),
        op_close(Axis.Y)
    )

    base = l.extrude(22) - Pos(l.a.arc_center) * Cylinder(22, d=13, align=A.d)
    base = mirror_add(base, Plane.YZ)

    c = RZ(-90) * Cylinder(36, d=30, align=A.d)
    _, edges = new_edges_add(c, Box(50, 30, 22, align=A.sd))
    part = fillet(edges.filter_by(Plane.XY), 6)
    part = base + (part & Box(30, 60, 100, align=A.d))

    part -= Cylinder(36, d=12, align=A.d)
    part -= Box(4, 9, 36, align=A.sd)
    part -= Pos(Y=69-15, Z=6+5) * Box(44+10*2, 42, 10, align=A.n)

    assert part.volume*densc == approx(328.02, abs=0.01)
    return part


@slist
@pytest.mark.views((10, 0))
def test_ppack_01_09():
    cl = build_line(Plane.XZ).append(
        op_line(angle=-45, until=YY(-45)),
        op_line(6, 90), op_line(angle=90, until=XX(0), name='l'),
    )

    p1 = split(make_slot(cl.l.length*2, h=-6, center=False, d=75),
               Plane.YZ.offset(-1))
    p1 -= X(cl.l.length-75/2) * Cylinder(12, d=33)
    p1 = cl.normal_loc(tangent=-1) * p1

    l2 = build_line(Y(60), Plane.YZ).append(
        op_arc(15, 75/2-90), op_line(until=XX(75/2)),
        YY(0), op_close(Axis.Y)
    )
    p2 = mirror_add(l2.extrude(-13))
    p2 -= Pos(l2[0].arc_center) * R.X * Cylinder(26, d=12)

    l3 = build_line().append(
        Y(-75/2), X(-69), Y(75), XX(0),
        op_fillet(17, 2), op_close()
    )
    p3 = l3.extrude(13)
    p3 -= mirror_add(Pos(17-69, 75/2-17, 13) * cbore_d(15, 4, 8, 13))

    _, edges = new_edges_add(p2+p3, p1)
    part = fillet(edges, 16)

    assert part.volume*densb == approx(307.23, abs=0.01)
    return part


@slist
def test_23_T_24_curved_support():
    r1, r2 = 55/2, 30/2

    l = build_line(Plane.XZ).append(
        op_arc(30, 90-8, center=(77-r1, 0)),
        op_line(until=XX(r1)),
        op_move(end=YY(50)),
        op_extend(end=5, reverse=True),
        op_trim(Axis.X.offset((125, 32)), add=True),
        op_fillet(66),
        op_close(Axis.X),
    )

    p1 = l.extrude(11/2, both=True)

    c1, c2 = Circle(r1), X(125) * Circle(r2)
    p2 = extrude(make_hull((c1 + c2).edges()), 11)

    cl1, cl2 = c1.cylinder(60), c2.cylinder(32)
    part = p1 + p2 + cl1 - cl1.new(d=35) + cl2 - cl2.new(d=20)

    assert part.volume*densc == approx(1294.13, abs=0.01)
    return part


if __name__ == '__main__':
    main_yacv()
