from __future__ import annotations

import pytest

from engine.context import MISSING
from engine.exceptions import UnknownOperatorError
from engine.operators import get_operator


def test_unknown_operator_raises():
    with pytest.raises(UnknownOperatorError):
        get_operator("does_not_exist")


@pytest.mark.parametrize(
    "op,actual,expected,result",
    [
        ("eq", "DE", "DE", True),
        ("eq", "DE", "US", False),
        ("eq", MISSING, "DE", False),
        ("neq", "DE", "US", True),
        ("neq", MISSING, "DE", True),
        ("gt", 600000, 500000, True),
        ("gt", 400000, 500000, False),
        ("gt", MISSING, 500000, False),
        ("gte", 500000, 500000, True),
        ("lt", 400000, 500000, True),
        ("lte", 500000, 500000, True),
        ("in", "DE", ["DE", "AT"], True),
        ("in", "US", ["DE", "AT"], False),
        ("in", MISSING, ["DE", "AT"], False),
        ("not_in", "US", ["DE", "AT"], True),
        ("not_in", MISSING, ["DE", "AT"], True),
        ("contains", ["a", "b"], "a", True),
        ("contains", ["a", "b"], "c", False),
        ("not_contains", ["a", "b"], "c", True),
        ("exists", "x", None, True),
        ("exists", MISSING, None, False),
        ("not_exists", MISSING, None, True),
        ("not_exists", "x", None, False),
        ("is_empty", [], None, True),
        ("is_empty", None, None, True),
        ("is_empty", MISSING, None, True),
        ("is_empty", ["a"], None, False),
        ("is_not_empty", ["a"], None, True),
        ("regex", "DE-123", r"^DE-\d+$", True),
        ("regex", "US-123", r"^DE-\d+$", False),
        ("between", 50, [10, 100], True),
        ("between", 5, [10, 100], False),
        ("between", MISSING, [10, 100], False),
    ],
)
def test_operator_results(op, actual, expected, result):
    fn = get_operator(op)
    assert fn(actual, expected) is result


def test_gt_type_mismatch_is_false_not_raising():
    fn = get_operator("gt")
    assert fn("abc", 5) is False
