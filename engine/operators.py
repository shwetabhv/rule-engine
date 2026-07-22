"""Registry of condition operators.

Rule authors reference these by name in JSON ("op": "eq", "in", "gt", ...).
Adding a genuinely new comparison primitive (rare) means adding one function
here with @operator("name") - it does NOT require touching the evaluator,
loader, or any existing rule file.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .context import MISSING
from .exceptions import UnknownOperatorError

Operator = Callable[[Any, Any], bool]

_REGISTRY: dict[str, Operator] = {}


def operator(name: str) -> Callable[[Operator], Operator]:
    def decorator(fn: Operator) -> Operator:
        if name in _REGISTRY:
            raise ValueError(f"Operator '{name}' is already registered")
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_operator(name: str) -> Operator:
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY))
        raise UnknownOperatorError(f"Unknown operator '{name}'. Available operators: {available}")


def available_operators() -> list[str]:
    return sorted(_REGISTRY)


@operator("eq")
def _eq(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    return actual == expected


@operator("neq")
def _neq(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return True
    return actual != expected


@operator("gt")
def _gt(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        return actual > expected
    except TypeError:
        return False


@operator("gte")
def _gte(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        return actual >= expected
    except TypeError:
        return False


@operator("lt")
def _lt(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        return actual < expected
    except TypeError:
        return False


@operator("lte")
def _lte(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        return actual <= expected
    except TypeError:
        return False


@operator("in")
def _in(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        return actual in expected
    except TypeError:
        return False


@operator("not_in")
def _not_in(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return True
    try:
        return actual not in expected
    except TypeError:
        return True


@operator("contains")
def _contains(actual: Any, expected: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        return expected in actual
    except TypeError:
        return False


@operator("not_contains")
def _not_contains(actual: Any, expected: Any) -> bool:
    return not _contains(actual, expected)


@operator("exists")
def _exists(actual: Any, _expected: Any = None) -> bool:
    return actual is not MISSING


@operator("not_exists")
def _not_exists(actual: Any, _expected: Any = None) -> bool:
    return actual is MISSING


@operator("is_empty")
def _is_empty(actual: Any, _expected: Any = None) -> bool:
    if actual is MISSING or actual is None:
        return True
    try:
        return len(actual) == 0
    except TypeError:
        return False


@operator("is_not_empty")
def _is_not_empty(actual: Any, _expected: Any = None) -> bool:
    return not _is_empty(actual)


@operator("regex")
def _regex(actual: Any, pattern: Any) -> bool:
    if actual is MISSING:
        return False
    return re.search(pattern, str(actual)) is not None


@operator("between")
def _between(actual: Any, bounds: Any) -> bool:
    if actual is MISSING:
        return False
    try:
        lo, hi = bounds
        return lo <= actual <= hi
    except (TypeError, ValueError):
        return False
