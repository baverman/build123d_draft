# repl-client
"""
## TTT Practice

[TTT practice][ttt-practice] is nice game mode for CADing.

Models here are augmented for spoil-free results.

[ttt-practice]: https://www.tootalltoby.com/practice/
"""
from build123d import *
from build123d_draft import *  # type: ignore[assignment]
from pytest import approx
import pytest

from build123d_draft.testing import *


LBF = 25.4**3 / 1000 / 0.45359237
densa = 1020e-6
densb = 2700e-6
densc = 7800e-6


@pytest.mark.views((0, -5))
def test_corner_cap() -> Part:
    """
    [Source](https://www.tootalltoby.com/practice/a441dcaa-0d1c-42f0-b037-73786e93a9ea).
    """
    l = build_line(Plane.XZ).append(
        YY(55), X(20), YY(9), XX(155), Y(-9),
        op_arc(start=Dir(FREE), end=(0, 0), r=560)
    )
    part = l.extrude(-60)

    edges = part.edges().filter_by(Axis.Z).group_by(Axis.X)[-1].group_by(Axis.Y)[0]
    part = fillet(edges, 16)

    part -= Pos(20, 30, 55-22) * R.X * cbore_d(30, 6, 20, 20)

    h = cbore_d(16, 5, 24, 18)
    part -= Pos(155-40, 20, 9) * h
    part -= Pos(155-40-60, 20, 9) * h

    rl = build_line(Plane.XZ.offset(-60)).append(
        YY(55-10), X(20+15), Y(10), (155, 9), op_close()
    )
    part += rl.extrude(7)

    assert part.volume*densa == approx(180.11, abs=0.01)
    return part


@pytest.mark.views((0, -5))
def test_lstop_simple() -> Part:
    """
    [Source](https://www.tootalltoby.com/practice/6926892f-c1e3-4d84-8ed8-359eb98d51b8).
    """
    l = build_line((130, 0), tangent=(0, 1)).append(
        op_arc(45, r=77).named('a'), op_trim(axis_offset(Axis.X, 25, 85/2), add=True),
        op_fillet(20), op_close(mirror=Axis.X)
    )
    part = l.extrude(12)

    s = make_hslot(start=25, center=l.a.arc_center, r=26, h=12+8)
    part = part + s - s.center_locs * cbore_d(25, 12, 13, 30)

    lr = build_line(Plane.XZ).append(
        op_line(start=Angle(90-15), end=YY(65)), op_close(XX(25))
    )
    rib = lr.extrude(85/2, both=True)

    h = Pos(25, 55/2, 65-10) * R.X * cbore_d(10, 5, 5, 30)
    rib -= mirror_add(h)
    rib -= Z(65) * R.X * make_hslot(center=20, r=15, h=30)
    part += rib

    assert part.volume*densa == approx(197.03, abs=0.01)
    return part


if __name__ == '__main__':
    main_yacv()
