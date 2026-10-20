# repl-client
"""
## TTT random models

A selection of TTT models from WC streams or other sources.
"""
from build123d import Plane, Pos, Part, Axis
from build123d_draft import *
from pytest import approx
import pytest

from tests.conftest import view
from build123d_draft.testing import *


LBF = 25.4**3 / 1000 / 0.45359237
densa = 1020e-6
densb = 2700e-6
densc = 7800e-6

@slist
def _test_model1() -> Part:
    l = build_line(Plane.XZ).append(
        YY(55), X(20), YY(9), XX(155), Y(-9),
        op_arc(start=Dir(FREE), end=(0, 0), r=560)
    )

    base = l.extrude(-60)
    base -= Pos(20, 30, 55-20) * R.X * cbore_d(34, 6, 26, 20)
    base -= Pos(155-40, 20, 9) * cbore(10, 5, 15, 20)
    base -= Pos(155-40-60, 20, 9) * cbore(10, 5, 15, 20)

    l = build_line(Plane.XZ.offset(-60)).append(
        YY(55-10), X(20+15), Y(10), (155, 9), op_close()
    )

    part = base + l.extrude(7)
    return part


@slist
@pytest.mark.views((30, 0), view(30, 0, clip=-Plane.XZ, hscale=0.02), size=(600, 480))
def test_24WC_12_tube_plug() -> Part:
    """
    [Draft](https://youtu.be/JrDNdeHMO9Q?t=71).

    Example uses additional variables for animation purposes.
    """
    l1 = build_line(Plane.XZ).append(
        op_start(X(150)), YY(111/2), X(-40), op_chamfer(8),
        YY(65/2), X(-23), YY(84/2), op_fillet(8, 2),
        XX(0), YY(0), op_fillet(10), op_close())
    part = l1.revolvex()

    l2 = build_line(Plane.XZ.move(X(150-109))).append(
        op_start(Y(88)), XX(70/2), Y(-30), op_chamfer(8),
        XX(58/2), YY(0), op_close(Axis.Y))
    p2 = l2.revolvey()
    part += p2

    hl = build_line(Plane.XZ).append(
        op_start(X(150)), X(-109), Y(88), op_fillet(30))
    hole = hl.sweep(Circle(d=40))
    part -= hole

    cl = build_line(Plane.XZ).append(
        op_start((150, 75/2), -Axis.X),
        op_line(start=Angle(44/2), end=YY(20)), op_close(Axis.X))
    cone = cl.revolvex()
    part -= cone

    assert part.volume*densa == approx(816.89, abs=0.01)
    return part


if __name__ == '__main__':
    main_ocp_vscode()
