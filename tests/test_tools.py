from build123d import *
from build123d_draft.tools import AX, AY


def test_rel_axis() -> None:
    ax = AY.to_axis(Plane.XZ)
    assert ax.direction == Vector(0, 0, 1)

    ax = AY(10).to_axis(Plane.XZ)
    assert ax.direction == Vector(0, 0, 1)
    assert ax.position == Vector(10, 0, 0)

    ax = AY(10).rotate(90).to_axis(Plane.XZ)
    assert ax.direction == Vector(-1, 0, 0)
    assert ax.position == Vector(10, 0, 0)
