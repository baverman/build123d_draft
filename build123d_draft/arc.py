from functools import cached_property, cache
from math import copysign
from typing import Literal, Callable, get_args, Any
from dataclasses import dataclass

from build123d import Vector, Edge, Pos, Axis, Plane
from build123d.topology.one_d import Mixin1D

from build123d_draft.build_line import (
    Constraint,
    AnyConstraint,
    build_line_op,
    build_line,
    VLike,
    AtDir,
    Free,
    FREE,
    AnyAxis,
    At,
    Angle,
)
from build123d_draft.tools import RelAxis, radius_arc

PT = Literal['S', 'Sd', 'St', 'Son', 'E', 'Ed', 'Et', 'Eon', 'P', 'C', 'Con', 'r', 'arc']
PTValues = get_args(PT)


@dataclass
class Context:
    plane: Plane
    params: dict[PT, object]
    short: bool = True


def arc_from_S_Sd_E(ctx: Context, S: Vector, Sd: Vector, E: Vector) -> Mixin1D[Any]:
    return Edge.make_tangent_arc(S, Sd, E)


def arc_from_S_E_r(ctx: Context, S: Vector, E: Vector, r: float) -> Mixin1D[Any]:
    return radius_arc(ctx.plane, S, E, r, short=ctx.short)


def point_dist(ctx: Context, P: Vector, O: Vector) -> float:
    return (P - O).length


def P_from_d_C_r(ctx: Context, d: Vector, C: Vector, r: float) -> Vector:
    return C - ctx.plane.z_dir.cross(d).normalized() * r


def point_tangent_with_center() -> None:
    raise NotImplementedError


def center_of_curves() -> None:
    raise NotImplementedError


def center_of_curves2() -> None:
    raise NotImplementedError


def point_with_center() -> None:
    raise NotImplementedError


def center_on_pcurve() -> None:
    raise NotImplementedError


def P_from_O_Od_r_Pd(ctx: Context, S: Vector, Sd: Vector, r: float, Ed: Vector) -> Vector:
    normal = ctx.plane.z_dir
    s2c = normal.cross(Sd).normalized()
    c = S + s2c * r
    c2e = normal.cross(Ed).normalized()
    return c - c2e * r


FT = Callable[..., object]
RuleDep = tuple[PT, ...]
Rule = tuple[tuple[RuleDep, ...], FT]
Plan = list[tuple[PT, FT, tuple[PT, ...]]]


@cache
def get_rules() -> dict[PT, list[Rule]]:
    result = {k: [(parse_rule(rule), fn) for rule, fn in rules] for k, rules in RULES.items()}
    # from pprint import pprint
    # pprint(result)
    return result


RULES: dict[PT, list[tuple[str, FT]]] = {
    'arc': [
        ('S Sd E', arc_from_S_Sd_E),
        ('S E r', arc_from_S_E_r),
    ],
    'r': [('P C', point_dist)],
    'Sd': [('S C', point_tangent_with_center)],
    'Ed': [('E C', point_tangent_with_center)],
    'C': [
        ('St Con', center_of_curves),
        ('Et Con', center_of_curves),
        ('St Et', center_of_curves2),
    ],
    'S': [
        ('Sd C r', P_from_d_C_r),
        ('St C', point_with_center),
    ],
    'E': [
        ('Ed C r', P_from_d_C_r),
        ('S Sd r Ed', P_from_O_Od_r_Pd),
        ('Et C', point_with_center),
    ],
    'Con': [
        ('S r', center_on_pcurve),
        ('E r', center_on_pcurve),
    ],
    'P': [('S|E', lambda ctx, x: x)],
}


def _check_dep(value: str) -> PT:
    assert value in PTValues
    return value  # type: ignore[return-value]


def parse_rule(rule: str) -> tuple[RuleDep, ...]:
    return tuple(tuple(_check_dep(it.strip()) for it in dep.split('|')) for dep in rule.split())


def _find_plan(
    target: PT,
    iparams: frozenset[PT],
    cache: dict[PT, bool],
    plan: Plan,
) -> bool:
    try:
        return cache[target]
    except KeyError:
        pass

    if target in iparams:
        cache[target] = True
        return True

    cache[target] = False

    rules = get_rules().get(target)
    if rules is None:
        return False

    for deps, fn in rules:
        args = []
        args_plan: Plan = []
        for depv in deps:
            for dep in depv:
                if _find_plan(dep, iparams, cache, args_plan):
                    args.append(dep)
                    break
        if len(args) == len(deps):
            plan.extend(args_plan)
            plan.append((target, fn, tuple(args)))
            cache[target] = True
            break

    return cache[target]


@cache
def find_plan(target: PT, iparams: frozenset[PT]) -> Plan:
    plan: Plan
    _find_plan(target, iparams, {}, plan:=[])
    return plan


def execute_plan(ctx: Context, plan: Plan) -> Mixin1D[Any]:
    values = ctx.params.copy()
    for p, fn, deps in plan:
        values[p] = fn(ctx, *[values[it] for it in deps])

    return values['arc']  # type: ignore[return-value]


def set_param(params: dict[PT, object], name: PT, value: Any) -> None:
    if value is not None:
        params[name] = value


@build_line_op
def op_arc(
    lb: build_line | None,
    end: float | VLike | Pos | AtDir | Free = FREE,
    start: float | VLike | Pos | AtDir | AnyConstraint | None = None,
    r: float | None = None,
    d: float | None = None,
    center: VLike | Pos | Edge | AnyAxis | None = None,
    short: bool = True,
) -> Mixin1D[Any] | None:
    if lb is None:
        return None

    if d is not None:
        r = d / 2

    center_on: Edge | Axis | None = None
    if isinstance(center, Edge):
        center_on = center
        ncenter = None
    elif isinstance(center, (Axis, RelAxis)):
        center_on = lb.to_axis(center)
        ncenter = None
    else:
        ncenter = lb.to_vector(center) if center is not None else None

    lbt = lb.tangent()

    if isinstance(start, (float, int)):
        start = Angle(start)

    if isinstance(start, AnyConstraint):
        spoint = sdir = None
        scon = Constraint.parse(lb, start)
    else:
        scon = None
        spoint, sdir = At.parse(lb, start, (lb.e, lbt), lbt)
        if r is not None and ncenter is not None:
            spoint = None

    if isinstance(end, (float, int)):
        end = Angle(end)

    epoint, edir = At.parse(lb, end, (FREE, FREE), sdir or lbt)
    if r is not None and ncenter is not None:
        epoint = None

    if r is not None and center is not None and sdir is not None and r is not None:
        sdir = lb.plane.z_dir.cross(sdir) * copysign(1, r)

    if r is not None and center is not None and edir is not None and r is not None:
        edir = lb.plane.z_dir.cross(edir) * copysign(1, r)

    params: dict[PT, object] = {}
    set_param(params, 'S', spoint)
    set_param(params, 'E', epoint)
    set_param(params, 'Sd', sdir)
    set_param(params, 'Ed', edir)
    set_param(params, 'C', ncenter)
    set_param(params, 'Con', center_on)
    set_param(params, 'r', r)
    if scon:
        set_param(params, 'St' if scon.is_tangent else 'Son', scon.value)

    iparams = frozenset(params)
    plan = find_plan('arc', frozenset(params))
    print(plan)

    if not plan:
        raise ValueError(f'Not enough constraints: {", ".join(params)}')

    ctx = Context(plane=lb.plane, params=params, short=short)
    result = execute_plan(ctx, plan)

    if result is None:
        raise ValueError(f'Error constructing arc')

    return lb.add_shape(result)


if __name__ == '__main__':
    from pprint import pprint
    import time

    s = time.perf_counter()
    sol = find_plan('arc', frozenset({'St', 'Con', 'r', 'Ed'}))
    print((time.perf_counter() - s) * 1000000)

    s = time.perf_counter()
    sol = find_plan('arc', frozenset({'St', 'Con', 'r', 'Ed'}))
    print((time.perf_counter() - s) * 1000000)

    pprint(sol)
