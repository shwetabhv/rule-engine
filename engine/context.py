"""Dot-path lookups into the evaluation context (client/account/product/loan data)."""

from __future__ import annotations

from typing import Any


class _Missing:
    """Sentinel distinguishing 'field absent' from 'field is None'."""

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


def get_field(context: dict[str, Any], path: str) -> Any:
    """Resolve a dotted path like 'client.address.country' against a nested dict.

    Returns MISSING (not None/KeyError) if any segment is absent, so operators
    can tell "field not present" apart from "field explicitly null".
    """
    current: Any = context
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return MISSING
    return current
