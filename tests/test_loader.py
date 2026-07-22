from __future__ import annotations

import pytest

from engine.exceptions import RuleValidationError
from engine.loader import RuleLoader

BASE_RULE = {
    "rule_id": "r1",
    "name": "Rule One",
    "product": "mortgage",
    "conditions": {"always": True},
    "actions": {"include_documents": [{"template_id": "doc_a"}]},
}


def test_load_valid_rules(rules_dir_factory):
    rules_dir = rules_dir_factory({"mortgage.json": [BASE_RULE]})
    loader = RuleLoader(rules_dir)
    rules = loader.load_rules()
    assert len(rules) == 1
    assert rules[0].rule_id == "r1"
    assert rules[0].product == ["mortgage"]


def test_missing_rules_dir_raises(tmp_path):
    loader = RuleLoader(tmp_path / "does_not_exist")
    with pytest.raises(RuleValidationError):
        loader.load_rules()


def test_malformed_json_raises(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
    loader = RuleLoader(rules_dir)
    with pytest.raises(RuleValidationError):
        loader.load_rules()


def test_duplicate_rule_id_raises(rules_dir_factory):
    dup = dict(BASE_RULE)
    rules_dir = rules_dir_factory({
        "a.json": [BASE_RULE],
        "b.json": [dup],
    })
    loader = RuleLoader(rules_dir)
    with pytest.raises(RuleValidationError, match="Duplicate rule_id"):
        loader.load_rules()


def test_invalid_condition_tree_raises(rules_dir_factory):
    bad_rule = dict(BASE_RULE, rule_id="bad", conditions={"all": []})
    rules_dir = rules_dir_factory({"a.json": [bad_rule]})
    loader = RuleLoader(rules_dir)
    with pytest.raises(RuleValidationError):
        loader.load_rules()


def test_load_templates(templates_file_factory):
    path = templates_file_factory([{"template_id": "doc_a", "name": "Doc A", "file": "a.docx"}])
    loader = RuleLoader(rules_dir="unused", templates_file=path)
    templates = loader.load_templates()
    assert set(templates) == {"doc_a"}


def test_load_templates_missing_file_raises(tmp_path):
    loader = RuleLoader(rules_dir="unused", templates_file=tmp_path / "nope.json")
    with pytest.raises(RuleValidationError):
        loader.load_templates()


def test_no_templates_file_returns_empty():
    loader = RuleLoader(rules_dir="unused", templates_file=None)
    assert loader.load_templates() == {}
