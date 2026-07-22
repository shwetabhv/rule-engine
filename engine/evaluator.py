"""Recursive evaluation of a condition tree against a context dict.

A condition node is one of:
  {"always": true|false}
  {"all": [node, ...]}          - AND, non-empty
  {"any": [node, ...]}          - OR, non-empty
  {"not": node}
  {"field": "a.b.c", "op": "eq", "value": ...}   - leaf comparison
"""

from __future__ import annotations

from typing import Any

from .context import get_field
from .exceptions import RuleValidationError, UnknownOperatorError
from .operators import get_operator


def validate_condition_tree(node: Any, path: str = "conditions") -> None:
    if not isinstance(node, dict):
        raise RuleValidationError(f"{path}: condition node must be a JSON object, got {type(node).__name__}")

    if "always" in node:
        if not isinstance(node["always"], bool):
            raise RuleValidationError(f"{path}.always must be a boolean")
        return

    if "all" in node:
        children = node["all"]
        if not isinstance(children, list) or not children:
            raise RuleValidationError(f"{path}.all must be a non-empty list")
        for i, child in enumerate(children):
            validate_condition_tree(child, f"{path}.all[{i}]")
        return

    if "any" in node:
        children = node["any"]
        if not isinstance(children, list) or not children:
            raise RuleValidationError(f"{path}.any must be a non-empty list")
        for i, child in enumerate(children):
            validate_condition_tree(child, f"{path}.any[{i}]")
        return

    if "not" in node:
        validate_condition_tree(node["not"], f"{path}.not")
        return

    missing = {"field", "op"} - set(node.keys())
    if missing:
        raise RuleValidationError(
            f"{path}: leaf condition missing {sorted(missing)}; expected 'field'+'op' "
            "or a grouping key ('all'/'any'/'not'/'always')"
        )
    if not isinstance(node["field"], str) or not node["field"]:
        raise RuleValidationError(f"{path}.field must be a non-empty string")
    if not isinstance(node["op"], str):
        raise RuleValidationError(f"{path}.op must be a string")
    # Resolving the operator now (rather than only at evaluation time) makes
    # a typo'd op name fail at load time instead of silently at runtime.
    try:
        get_operator(node["op"])
    except UnknownOperatorError as e:
        raise RuleValidationError(f"{path}.op: {e}") from e


def evaluate(node: dict[str, Any], context: dict[str, Any]) -> bool:
    if "always" in node:
        return bool(node["always"])
    if "all" in node:
        return all(evaluate(child, context) for child in node["all"])
    if "any" in node:
        return any(evaluate(child, context) for child in node["any"])
    if "not" in node:
        return not evaluate(node["not"], context)

    actual = get_field(context, node["field"])
    fn = get_operator(node["op"])
    return fn(actual, node.get("value"))
