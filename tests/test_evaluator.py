from __future__ import annotations

import pytest

from engine.evaluator import evaluate, validate_condition_tree
from engine.exceptions import RuleValidationError


def test_always_true():
    assert evaluate({"always": True}, {}) is True


def test_always_false():
    assert evaluate({"always": False}, {}) is False


def test_leaf_condition():
    assert evaluate({"field": "client.country", "op": "eq", "value": "DE"}, {"client": {"country": "DE"}}) is True


def test_all_group():
    node = {"all": [
        {"field": "client.country", "op": "eq", "value": "DE"},
        {"field": "loan.amount", "op": "gt", "value": 1000},
    ]}
    ctx_match = {"client": {"country": "DE"}, "loan": {"amount": 2000}}
    ctx_no_match = {"client": {"country": "DE"}, "loan": {"amount": 500}}
    assert evaluate(node, ctx_match) is True
    assert evaluate(node, ctx_no_match) is False


def test_any_group():
    node = {"any": [
        {"field": "client.country", "op": "eq", "value": "DE"},
        {"field": "client.country", "op": "eq", "value": "AT"},
    ]}
    assert evaluate(node, {"client": {"country": "AT"}}) is True
    assert evaluate(node, {"client": {"country": "US"}}) is False


def test_not_group():
    node = {"not": {"field": "client.country", "op": "eq", "value": "DE"}}
    assert evaluate(node, {"client": {"country": "US"}}) is True
    assert evaluate(node, {"client": {"country": "DE"}}) is False


def test_nested_groups():
    node = {
        "all": [
            {"field": "client.nationality", "op": "in", "value": ["IR", "KP", "SY"]},
            {"not": {"field": "account.country", "op": "eq", "value": "DE"}},
        ]
    }
    assert evaluate(node, {"client": {"nationality": "IR"}, "account": {"country": "US"}}) is True
    assert evaluate(node, {"client": {"nationality": "IR"}, "account": {"country": "DE"}}) is False
    assert evaluate(node, {"client": {"nationality": "FR"}, "account": {"country": "US"}}) is False


def test_missing_field_is_safe_not_an_error():
    node = {"field": "client.country", "op": "eq", "value": "DE"}
    assert evaluate(node, {}) is False


# --- validation ---

def test_validate_leaf_ok():
    validate_condition_tree({"field": "a.b", "op": "eq", "value": 1})


def test_validate_rejects_non_dict():
    with pytest.raises(RuleValidationError):
        validate_condition_tree("not a dict")


def test_validate_rejects_empty_all():
    with pytest.raises(RuleValidationError):
        validate_condition_tree({"all": []})


def test_validate_rejects_empty_any():
    with pytest.raises(RuleValidationError):
        validate_condition_tree({"any": []})


def test_validate_rejects_leaf_missing_op():
    with pytest.raises(RuleValidationError):
        validate_condition_tree({"field": "a.b"})


def test_validate_rejects_unknown_operator():
    with pytest.raises(RuleValidationError):
        validate_condition_tree({"field": "a.b", "op": "totally_made_up"})


def test_validate_recurses_into_groups():
    with pytest.raises(RuleValidationError):
        validate_condition_tree({"all": [{"field": "a.b", "op": "eq", "value": 1}, {"field": "bad"}]})
