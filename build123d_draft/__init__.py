import math
from typing import TypeVar, Callable

from build123d import geometry as _gm
from build123d import topology as _tp
from build123d import build_enums as _be

from build123d_draft.tools import *

_T = TypeVar('_T')
dpr = math.pi / 180
sqr2 = math.sqrt(2)


def gen_pos(
    name: str, cls: type[_T], default_zdir: tuple[float, float, float] | None = None
) -> Callable[[float], _T]:
    def g(val: float) -> _T:
        rv = cls(**{name: val})
        rv.default_zdir = default_zdir  # type: ignore[attr-defined]
        return rv

    return g


def gen_rot(name: str) -> Callable[[float], _gm.Rot]:
    def g(val: float) -> _gm.Rot:
        return _gm.Rot(**{name: val})  # type: ignore[no-any-return,call-overload]

    return g


X = gen_pos('X', _gm.Pos, default_zdir=(1, 0, 0))
Y = gen_pos('Y', _gm.Pos, default_zdir=(0, 1, 0))
Z = gen_pos('Z', _gm.Pos, default_zdir=(0, 0, 1))
XX = gen_pos('X', PPos, default_zdir=(1, 0, 0))
YY = gen_pos('Y', PPos, default_zdir=(0, 1, 0))
ZZ = gen_pos('Z', PPos, default_zdir=(0, 0, 1))

RX = gen_rot('X')
RY = gen_rot('Y')
RZ = gen_rot('Z')

_AMAP = {
    'w': (0, _be.Align.MIN),
    'e': (0, _be.Align.MAX),
    's': (1, _be.Align.MIN),
    'n': (1, _be.Align.MAX),
    'd': (2, _be.Align.MIN),
    'u': (2, _be.Align.MAX),
}


class R:
    X = RY(90)
    Y = RX(-90)


class _A:
    X = _gm.Axis.X
    Y = _gm.Axis.Y
    Z = _gm.Axis.Z

    default = [_be.Align.CENTER, _be.Align.CENTER, _be.Align.CENTER]

    # TODO: clarify 2d and 3d align variants
    def __getattr__(self, desc: str) -> _be.Align:
        result = self.default[:]
        for c in desc:
            try:
                p, a = _AMAP[c]
            except KeyError:
                raise AttributeError(desc)
            result[p] = a
        return tuple(result)  # type: ignore[return-value]


A = _A()


_gm.Vector.perpendicular = lambda self, raxis=_gm.Axis.Z: self.rotate(raxis, 90)  # type: ignore[attr-defined]
_gm.Vector.rot = lambda self, angle, raxis=_gm.Axis.Z: self.rotate(raxis, angle)  # type: ignore[attr-defined]
_tp.Mixin1D.at = lambda self, param: self.position_at(param)  # type: ignore[attr-defined]
_tp.Mixin1D.tat = lambda self, param: self.tangent_at(param)  # type: ignore[attr-defined]
_tp.Mixin1D.nat = lambda self, param, raxis=_gm.Axis.Z: self.tangent_at(param).perpendicular(raxis)  # type: ignore[attr-defined]
_gm.Axis.offset = axis_offset  # type: ignore[attr-defined]
_tp.Shape.arc_center = property(lambda self: self.edge().arc_center)
_tp.Mixin1D.s = property(lambda self: self.position_at(0))  # type: ignore[attr-defined]
_tp.Mixin1D.e = property(lambda self: self.position_at(1))  # type: ignore[attr-defined]

from build123d_draft.build_line import *
