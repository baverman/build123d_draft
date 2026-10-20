# repl-client
"""
## TTT Challenges

A selection of models from [TTT Challenges][ttt-challenges].
It's a monthly competition with available drafts and final
part mass. It's an easiest way to train your skills.

[ttt-challenges]: https://www.tootalltoby.com/Leaderboard/
"""
from build123d import (Pos, Plane, fillet, Box, Axis, CounterSinkHole, revolve, offset, split,
    make_face, Keep, PolarLocations, extrude, Side, Part, Vector, make_hull, RectangleRounded)
from build123d_draft import *
from pytest import approx
import pytest

from build123d_draft.testing import *


LBF = 25.4**3 / 1000 / 0.45359237
densa = 1020e-6
densb = 2700e-6
densc = 7800e-6


@slist
@pytest.mark.views(None, (0, 70), size=(480, 480))
def test_24_04_LB1_u_joint_fork() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-04/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/D_LEADERBOARD_CHALLENGE_MODEL_1_IMAGE_-_APRIL.png).
    """
    l1 = build_line(Plane.XZ).append(
        X(42/2), Y(51), op_fillet(12),
        X(14), YY(-14), XX(0), op_fillet(26),
        op_close(),
    )
    part = l1.extrude(38/2+1, both=True) # +1 to give space for fillet

    l2 = build_line(Plane.YZ).append(
        op_arc(start=Y(51), end=17/2-90, r=-15),
        op_line(end=XX(38/2)), YY(0), op_fillet(115),
        X(5), op_close(axis_offset(Axis.X, Y=60))
    )
    part -= mirror_add(l2.extrude(100))

    loc = Pos(X=70/2, Z=51-15) * R.X
    part += loc * Cylinder(70/2-36/2, r=15, align=A.u)
    part -= loc * CounterSinkHole(13/2, 19/2, 50, 100)
    part = mirror_add(part, Plane.YZ)

    b = 51 - 15 - 65
    c = Z(b) * Cylinder(abs(-5 - b), d=32, align=A.d)
    part, edges = new_edges_add(c, part)
    part = fillet(edges, 3)
    part -= mirror_add(Y(-38/2) * Box(100, 5, 14, align=A.nu))

    part -= c.new(50, d=21)

    assert part.volume*densc == approx(589.04, abs=0.01)
    return part


@slist
def test_22_T_32_pivot_plate() -> Part:
    l = build_line(Plane.XZ).append(
        Y(2.625-1.5), op_arc(-180, d=-3).named('a'),
        op_trim(axis_offset(Axis.X, 4, 1.5), add=True),
        op_fillet(0.75),
        op_close(Axis.X)
    )
    p1 = l.extrude(-0.25)
    p1 -= Pos(l.a.arc_center) * R.Y * Cylinder(1, d=0.5)
    p1 = mirror_add(Y(-5/2) * p1)

    part = p1 + Box(4, 5, 0.25, align=A.wd)
    part += X(4) * Box(2, 3, 1.25, align=A.ed)

    c = X(3) * Cylinder(2, d=1.75, align=A.d)
    part = part + c - c.new(d=0.625)

    assert part.volume*densb*LBF == approx(1.543, abs=0.001)
    return part


@slist
@pytest.mark.views(None, (-90, 0), size=(480, 480))
def test_24_05_LB1_clamp_bracket() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-05/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/D_LEADERBOARD_CHALLENGE_MODEL_1_IMAGE_-_MAY.png).
    """
    l1 = build_line((-133/2, 12)).append(
        op_line(start=Dir((1, 0), angle=19), end=XX(0)),
        op_line(start=Dir((1, 0), angle=-19), end=XX(133/2)),
        op_fillet(33), op_close(mirror=Axis.X)
    )
    p1 = l1.extrude(20)
    p1 -= mirror_add(Pos(99/2, Z=20) * cbore(12, 5, 6, 20), Plane.YZ)

    l2 = build_line(Y(33)).append(
        op_arc(-180, r=-33),
        op_trim(axis_offset(Axis.Y, 44/2, -55-15), add=True),
        op_fillet(30), op_close(mirror=Axis.Y)
    )
    p2 = l2.extrude(41)

    edges = p2.edges().filter_by(Axis.X).group_by(
        Axis.Z)[-1].group_by(Axis.Y)[0]
    p2 = fillet(edges, 15)
    p2 -= Pos(44/2, -55, 26) * R.X * cbore(12, 5, 6, 44)

    part = p1 + p2
    part -= Cylinder(41, d=42, align=A.d)
    part -= Box(8, 55+15, 41, align=A.nd)

    assert part.volume*densa == approx(183.03, abs=0.01)
    return part


@slist
@pytest.mark.views((45, 0), (45, 70), size=(480, 480))
def test_24_05_LB2_chamber() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-05/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/E_LEADERBOARD_CHALLENGE_MODEL_2_IMAGE_-_MAY.png).
    """
    l = build_line((5.5/2, 3.5), Plane.XZ, Y(-1)).append(
        op_line(start=Angle(-10), end=YY(0.75)), XX(0)
    )
    sk = offset(l.wire(), 0.375, side=Side.RIGHT)

    l.append(op_close(Axis.Y))
    bowl = l.revolvey()

    p1 = revolve(split(make_face(sk.edges()), Plane.XY.offset(3.5),
                       keep=Keep.BOTTOM))

    sl = make_slot(6.5, h=1.75, r=0.375)
    p2 = sl - sl.center_locs * Cylinder(1.75, d=.41, align=A.u)

    part = p1 + (RZ(45) * p2 + RZ(90+45) * p2 - bowl)

    loch = Z(0.75)
    rib = loch * Box(5.5/2, 0.25, 3.5-0.75*2, align=A.wd)
    part += PolarLocations(0, 3, 60) * (bowl & rib)

    part += loch * Cylinder(3.5-0.5-0.75, d=1.25, align=A.d)
    part -= Cylinder(3.5-0.5, d=0.75, align=A.d)

    assert part.volume*densc*LBF == approx(9.1806, abs=0.0001)
    return part


@slist
def test_24_05_LB3_arm_housing() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-05/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/F_LEADERBOARD_CHALLENGE_MODEL_3_IMAGE_-_MAY.png).
    """
    l = build_line(Plane.XZ).append(
        X(38/2), Y(51-12), XX(72/2), YY(78+20), op_fillet(16),
        X(-12), YY(51), XX(0), op_fillet(4), op_close()
    )
    p1 = l.extrude(20, both=True)

    # TODO: transform slot center locations
    sl = X(72/2) * -R.X * make_slot(78*2, h=12, d=40)
    p1 = split(p1, Plane.YZ.offset(72/2-12), keep=Keep.BOTTOM) + (p1 & sl)
    p1 -= Pos(72/2, Z=78) * R.X * Cylinder(24, d=19)
    p1 = mirror_add(p1, Plane.YZ)

    c1 = R.X * Cylinder(55, d=66)
    c2 = Cylinder(40, d=36, align=A.u)
    part = p1 + c1 + c2 - c2.new(d=18) - c1.new(d=40)

    assert part.volume*densb == approx(538.04, abs=0.01)
    return part


@slist
@pytest.mark.views((-90, 0))
def test_24_07_LB3_adj_base() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-07/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/F_LEADERBOARD_CHALLENGE_MODEL_3_IMAGE_-_JULY.png).
    """
    c1 = X(127) * Circle(d=25)
    c2 = Circle(d=45)
    c3 = Pos(Vector(1, 0).rotate(Axis.Z, 60) * 127) * Circle(d=25)

    base_sk = make_hull((c1 + c2).edges()) + make_hull((c2 + c3).edges())
    base_sk = fillet(base_sk.vertices().group_by(Axis.X)[2], 13)
    base = extrude(base_sk, 6)
    base.clean()

    cl1 = c1.cylinder(25)
    cl2 = c2.cylinder(57)
    cl3 = c3.cylinder(25)

    rl = build_line((c2.radius, 55), Plane.XZ).append(
        (127-c3.radius, 23),
        op_extend(start=YY(56), end=XX(127)),
        op_close(Axis.X)
    )
    rib = rl.extrude(3, both=True)

    cset = cl1 + cl2 + cl3
    part = base - cset + cset + rib + RZ(60) * rib
    part -= cl1.new(d=13) + cl2.new(d=29) + cl3.new(d=13)

    assert part.volume*densb == approx(398.09, abs=0.01)
    return part


@slist
@pytest.mark.views((110, 0))
def test_24_07_LB1_foot_holder() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-07/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/D_LEADERBOARD_CHALLENGE_MODEL_1_IMAGE_-_JULY.png).
    """
    c = Cylinder(12, d=136, align=A.d)
    c -= mirror_add(Pos(Y=105/2, Z=12) * cbore_d(16, 5, 8, 12))

    loc = X(-62/2)
    part = c + loc * make_slot(62, h=66, r=42)
    part -= Z(18) * loc * make_slot(62, h=66-18, r=42-12)

    l = build_line(Plane.XZ).append(
        op_line(start=At((-52, 18), angle=45), end=YY(66)),
        op_close(Plane.YZ.offset(-200))
    )
    part -= l.extrude(100, both=True)
    part -= make_slot(62*2, h=18, r=19)
    part -= Box(100, 19*2, 18, align=A.wd)
    part -= R.X * make_slot(32*2, h=50, r=19)
    part -= Pos(X=-62-42, Z=9) * -R.X * CounterSinkHole(6/2, 14/2, 50, 82)

    assert part.volume*densc == approx(2013.97, abs=0.01)
    return part


@slist
def test_24_04_LB2_rod_end_mount() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-04/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/E_LEADERBOARD_CHALLENGE_MODEL_2_IMAGE-APRIL.png).
    """

    c = R.X * Cylinder(1.375, d=1.125, align=A.d)
    part = c + c.new(7-1, d=0.875) + c.new(7, d=0.5)
    cut = X(7) * Z(0.375/2) * Box(.75, 1, 1, align=A.de)
    part -= mirror_add(cut, Plane.XY)

    r = 2.25/2
    l1 = build_line(Pos(r, 1.5/2-0.01), Plane.XZ).append(
        op_line(start=Angle(-10), end=YY(0)),
        op_extend(start=YY(1.5/2-0.001)),
        op_close(mirror=Axis.X),
    )
    part += l1.extrude(.25/2, both=True)

    l2 = build_line().append(
        op_arc(start=Y(r), end=-14, r=-r),
        op_line(end=YY(0)),
        op_drop(),
        op_close(mirror=Axis.X),
    )
    part += l2.extrude(.25/2, both=True)

    c = Cylinder(1.5, r=r)
    part = part + c - c.new(d=1.5)

    assert part.volume*densb*LBF == approx(0.675, abs=0.00001)
    return part


@slist
@pytest.mark.views((10, 5), (100, 15))
def test_24_04_LB3_end_base() -> Part:
    """
    [Source](https://www.tootalltoby.com/challenge/2024-04/drawings/).
    [Draft](https://www.tootalltoby.com/media/challenges/events/models/F_LEADERBOARD_CHALLENGE_MODEL_3_IMAGE_-_APRIL_SS11zYc.png).
    """

    l = build_line(Pos(218, 22), Plane.XZ).append(
        XX(175-25),
        op_line(start=Angle(25), end=YY(14)),
        XX(22), YY(88), XX(0),
        op_close(Axis.X)
    )
    part = l.extrude(-50)
    part = split(part, Plane.XZ.moved(Pos(188, 0, -50)).rotated((0, 0, -45)))

    l = build_line(plane=Plane.XZ.offset(-50)).append(
        op_line(start=(22, 88), end=(188, 22)),
        op_close(Axis.X)
    )
    part += l.extrude(8)
    part = mirror_add(part)

    part -= Z(88/2) * R.X * extrude(
        RectangleRounded(88-16, 100-16, 11), 22-10)
    part -= Z(88-24) * R.X * make_slot(14, h=30, r=9, rotation=90)

    l = build_line(X(175-30)).append(
        op_line(start=Angle(60), end=YY(52/2)),
        op_close(axis_offset(Axis.Y, X=230))
    )
    part -= mirror_add(l.extrude(12))
    part -= X(218) * make_slot((218-175)*2, h=30, d=28)

    assert part.volume*densa == approx(490.05, abs=0.01)
    return part


@slist
@pytest.mark.views((15, 10))
def test_2024_03_10_offset_support() -> Part:
    """
    [Source](https://www.tootalltoby.com/leaderboard/2024-03/).
    [Draft](https://www.tootalltoby.com/static/images/2024-03_LEADERBOARD_CHALLENGE_MODEL_1_IMAGE.png).
    """
    l = build_line(Plane.XZ).append(
        op_line(start=At((69, 10), angle=50), end=XX(80+33)), YY(70),
        op_arc(start=At((0, 70), (-1, 0)), end=90, r=90),
        op_trim(axis_offset(Axis.X, Y=15)),
        op_move(end=(0, 15)).connected,
        op_close(Axis.X)
    )
    part = l.extrude(5, both=True)

    c = Pos(80+33, 0, 70) * Cylinder(30, d=35, align=A.u)
    part = part + c - c.location * cbore_d(25, 7, 15, 30)

    part += extrude(RectangleRounded(69, 75, 8, align=A.w), 15)
    part -= mirror_add(Pos(33, 40/2) * Cylinder(15, d=12, align=A.d))

    lc = build_line(Plane.XZ).append(
        op_line(start=At(XX(12), angle=30), end=Y(5)),
        op_close(mirror=axis_offset(Axis.Y, 69/2)),
    )
    part -= lc.extrude(100, both=True)

    assert part.volume*densb == approx(322.20, abs=0.01)
    return part


@slist
def test_2024_03_12_side_spacer() -> Part:
    """
    [Source](https://www.tootalltoby.com/leaderboard/2024-03/).
    [Draft](https://www.tootalltoby.com/static/images/2024-03_LEADERBOARD_CHALLENGE_MODEL_3_IMAGE.png).
    """

    l = build_line().append(
        op_arc(start=At(X(60+50), (0, 1)), end=90, r=50),
        op_trim(axis_offset(Axis.X, Y=40)),
        op_line(start=Dir((1, 0), angle=15), end=XX(60+196)),
        op_drop(), op_close(mirror=Axis.X)
    )
    part: Part = l.extrude(20)

    c = X(60+196) * Cylinder(35, r=95, align=A.d)
    part = part + c - c.new(r=75)
    part = split(part, Plane.YZ.offset(c.location.position.X),
                 keep=Keep.BOTTOM)

    s1 = make_hslot((-40, 60), h=40, r=50, both=True)
    s2 = -R.Y * make_hslot((60+50, 0), h=50, r=40, both=True)
    part = part + Z(40) * (s1 & s2)

    part -= Pos(60) * Cylinder(80, d=42, align=A.d)
    part -= mirror_add(Pos(0, -50, 40) * -R.Y * CounterSinkHole(
        33/2, 33/2+8, 50, 90))

    l = build_line(Plane.XZ).append(
        op_line(start=At(Pos(60+50, 80-20), angle=-30), end=XX(60+196-95)),
        op_extend(5, 5), op_close(Axis.X)
    )
    part += l.extrude(6, both=True)

    assert part.volume*densa == approx(1204.07, abs=0.01)
    return part


if __name__ == '__main__':
    main_ocp_vscode()
