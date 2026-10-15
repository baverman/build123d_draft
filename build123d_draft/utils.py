import sys

from typing import Iterable, Mapping


def _defined(*args: object) -> bool:
    return any(it is not None for it in args)


def _defined_all(*args: object) -> bool:
    return all(it is not None for it in args)


_Arg = str | None | list['_Arg'] | tuple['_Arg', ...]


def _iter_args(col: Iterable[_Arg]) -> Iterable[str]:
    for it in col:
        if type(it) is str:
            yield it.lstrip('+-!')
        elif it is None:
            pass
        else:
            yield from _iter_args(it)


def _eval_args(vals: Mapping[str, object], case: _Arg) -> bool:
    tcase = type(case)
    if tcase is str:
        cv: str = case  # type: ignore[assignment]
        if cv[0] == '+':
            v = vals[cv[1:]]
            return v is not False and v is not None
        elif cv[0] == '!':
            return vals[cv[1:]] is False
        elif cv[0] == '-':
            return vals[cv[1:]] is None
        return vals[cv] is not None
    elif tcase is list:
        listv: list[str] = case  # type: ignore[assignment]
        return all(_eval_args(vals, it) for it in listv)
    elif tcase is tuple:
        tuplev: tuple[str, ...] = case  # type: ignore[assignment]
        mc = sum(_eval_args(vals, it) for it in tuplev)
        if tuplev[0] is None:
            return mc <= 1
        return mc == 1
    elif case is None:
        return False
    return False


def assert_args(vals: Mapping[str, object], *cases: _Arg) -> None:
    matched_count = sum(_eval_args(vals, it) for it in cases)
    if matched_count == 1:
        return

    assert False, f'matched_cases={matched_count}: ' + str(cases)


def debug(*args: object, **kwargs: object) -> None:
    kwargs['file'] = sys.stderr
    print(*args, **kwargs)  # type: ignore[call-overload]
