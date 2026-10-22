import sys
import functools
from typing import TypeVar, Callable, ParamSpec, Any

from build123d import Sphere, Shape

from .build_line import build_line

ShowObject = Shape[Any] | build_line
P = ParamSpec('P')
R = TypeVar('R')

_current_fn: Callable[[], ShowObject | None] | None = None


def set_current(fn: Callable[[], ShowObject | None]) -> Callable[[], ShowObject | None]:
    global _current_fn
    import pytest

    _current_fn = fn
    return pytest.mark.current(fn)


class ShowList:
    def __init__(self) -> None:
        self.objects: list[ShowObject] = []
        self.names: list[str] = []
        self.cnt = 0

    def reset(self) -> None:
        self.objects.clear()
        self.names.clear()
        self.cnt = 0

    def origin_radius(self) -> float:
        if not self.objects:
            return 1
        o = self.objects[-1]
        if hasattr(o, 'bounding_box'):
            bbox = o.bounding_box()
            if bbox.diagonal > 20:
                return 1
            else:
                return 0.1
        else:
            return 1

    def append(self, *items: ShowObject | None, **kwargs: ShowObject | None) -> None:
        olist = []
        if items:
            fl = sys._getframe(1).f_locals
            fmap = {id(v): k for k, v in fl.items()}
            for o in items:
                k = id(o)
                if k in fmap:
                    n = fmap[k]
                else:
                    self.cnt += 1
                    n = f'unknown_var_{self.cnt}'
                olist.append((n, o))

        olist.extend(kwargs.items())

        for n, o in olist:
            if o is None:
                continue
            if isinstance(o, build_line):
                o = o.wire()
            self.objects.append(o)
            self.names.append(n)


slist = ShowList()
sadd = slist.append


def main_yacv() -> None:
    from yacv_server import show  # type: ignore

    if _current_fn:
        slist.reset()
    sadd(origin=Sphere(1))
    if _current_fn:
        slist.append(result=_current_fn())
    show(*slist.objects, names=slist.names)


def main_ocp_vscode(**options: object) -> None:
    from ocp_vscode import show, set_port, set_defaults  # type: ignore[import-untyped]
    from ocp_vscode.config import Camera  # type: ignore[import-untyped]

    set_port(options.pop('port', 3939))
    # if options:
    #     set_defaults(**options)

    if _current_fn:
        slist.reset()
        slist.append(result=_current_fn())
    show(*slist.objects, names=slist.names, progress='', reset_camera=Camera.KEEP)


__all__ = ['slist', 'sadd', 'main_yacv', 'set_current', 'main_ocp_vscode']
