from __future__ import annotations

from datetime import date

import pytest

from engine.engine import RuleEngine
from engine.exceptions import RuleValidationError


@pytest.fixture
def sample_engine(sample_rules_dir, sample_templates_file):
    return RuleEngine(sample_rules_dir, sample_templates_file, strict_templates=True)


def doc_ids(result):
    return {d.template_id for d in result.documents}


def test_mortgage_baseline_english_docs(sample_engine):
    result = sample_engine.evaluate("mortgage", {"client": {}, "account": {}, "loan": {}})
    assert doc_ids(result) == {"parent_contract_en", "mortgage_contract_en", "kyc_form_en"}
    assert result.variables["language"] == "en"
    assert "mortgage_base_docs" in result.matched_rule_ids


def test_mortgage_germany_overrides_language(sample_engine):
    ctx = {"client": {}, "account": {"country": "DE"}, "loan": {}}
    result = sample_engine.evaluate("mortgage", ctx)
    ids = doc_ids(result)
    assert "mortgage_contract_de" in ids
    assert "kyc_form_de" in ids
    assert "mortgage_contract_en" not in ids
    assert "kyc_form_en" not in ids
    assert result.variables["language"] == "de"


def test_mortgage_high_value_loan_adds_enhanced_kyc(sample_engine):
    ctx = {"client": {}, "account": {}, "loan": {"amount": 750000}}
    result = sample_engine.evaluate("mortgage", ctx)
    assert "kyc_enhanced_form_en" in doc_ids(result)


def test_mortgage_high_risk_client_adds_enhanced_kyc(sample_engine):
    ctx = {"client": {"risk_rating": "high"}, "account": {}, "loan": {"amount": 1000}}
    result = sample_engine.evaluate("mortgage", ctx)
    assert "kyc_enhanced_form_en" in doc_ids(result)


def test_mortgage_low_value_loan_no_enhanced_kyc(sample_engine):
    ctx = {"client": {"risk_rating": "low"}, "account": {}, "loan": {"amount": 1000}}
    result = sample_engine.evaluate("mortgage", ctx)
    assert "kyc_enhanced_form_en" not in doc_ids(result)


def test_mortgage_sanctions_disclosure_for_watchlist_nationality_abroad(sample_engine):
    ctx = {"client": {"nationality": "IR"}, "account": {"country": "US"}, "loan": {}}
    result = sample_engine.evaluate("mortgage", ctx)
    assert "sanctions_disclosure_en" in doc_ids(result)


def test_mortgage_sanctions_disclosure_suppressed_for_domestic_de_account(sample_engine):
    ctx = {"client": {"nationality": "IR"}, "account": {"country": "DE"}, "loan": {}}
    result = sample_engine.evaluate("mortgage", ctx)
    assert "sanctions_disclosure_en" not in doc_ids(result)


def test_unknown_product_matches_no_rules(sample_engine):
    result = sample_engine.evaluate("totally_unknown_product", {})
    assert result.documents == []
    assert result.matched_rule_ids == []
    assert all(not t.matched for t in result.trace)


def test_auto_loan_before_regulation_effective_date_has_no_note(sample_engine):
    ctx = {}
    result = sample_engine.evaluate("auto_loan", ctx, as_of=date(2025, 6, 1))
    kyc = next(d for d in result.documents if d.template_id == "kyc_form_en")
    assert "note" not in kyc.variables
    assert "auto_loan_new_disclosure_2026" not in result.matched_rule_ids


def test_auto_loan_after_regulation_effective_date_overrides_kyc(sample_engine):
    ctx = {}
    result = sample_engine.evaluate("auto_loan", ctx, as_of=date(2026, 2, 1))
    kyc = next(d for d in result.documents if d.template_id == "kyc_form_en")
    assert kyc.variables.get("note") == "regulatory_disclosure_v2026"
    assert kyc.matched_rule_id == "auto_loan_new_disclosure_2026"


def test_trace_includes_every_rule(sample_engine):
    result = sample_engine.evaluate("mortgage", {})
    traced_ids = {t.rule_id for t in result.trace}
    all_rule_ids = {r.rule_id for r in sample_engine.rules}
    assert traced_ids == all_rule_ids


# --- conflict resolution & inactive/effective-date behavior, via synthetic rules ---


def test_lower_priority_number_wins_include_conflict(rules_dir_factory, templates_file_factory):
    templates = templates_file_factory([
        {"template_id": "doc_a", "name": "A", "file": "a.docx"},
    ])
    rules_dir = rules_dir_factory({
        "p.json": [
            {
                "rule_id": "high_precedence",
                "name": "High precedence",
                "product": "*",
                "priority": 1,
                "conditions": {"always": True},
                "actions": {"include_documents": [{"template_id": "doc_a", "variables": {"who": "high"}}]},
            },
            {
                "rule_id": "low_precedence",
                "name": "Low precedence",
                "product": "*",
                "priority": 50,
                "conditions": {"always": True},
                "actions": {"include_documents": [{"template_id": "doc_a", "variables": {"who": "low"}}]},
            },
        ]
    })
    engine = RuleEngine(rules_dir, templates, strict_templates=True)
    result = engine.evaluate("any_product", {})
    doc = next(d for d in result.documents if d.template_id == "doc_a")
    assert doc.variables["who"] == "high"
    assert doc.matched_rule_id == "high_precedence"


def test_exclude_wins_regardless_of_priority(rules_dir_factory, templates_file_factory):
    templates = templates_file_factory([{"template_id": "doc_a", "name": "A", "file": "a.docx"}])
    rules_dir = rules_dir_factory({
        "p.json": [
            {
                "rule_id": "includer",
                "name": "Includer",
                "product": "*",
                "priority": 1,
                "conditions": {"always": True},
                "actions": {"include_documents": [{"template_id": "doc_a"}]},
            },
            {
                "rule_id": "excluder",
                "name": "Excluder",
                "product": "*",
                "priority": 100,
                "conditions": {"always": True},
                "actions": {"exclude_documents": ["doc_a"]},
            },
        ]
    })
    engine = RuleEngine(rules_dir, templates, strict_templates=True)
    result = engine.evaluate("any_product", {})
    assert result.documents == []


def test_inactive_rule_never_matches(rules_dir_factory):
    rules_dir = rules_dir_factory({
        "p.json": [
            {
                "rule_id": "disabled",
                "name": "Disabled",
                "product": "*",
                "is_active": False,
                "conditions": {"always": True},
                "actions": {"include_documents": [{"template_id": "doc_a"}]},
            }
        ]
    })
    engine = RuleEngine(rules_dir)
    result = engine.evaluate("any_product", {})
    assert result.documents == []
    assert result.trace[0].active is False
    assert result.trace[0].matched is False


def test_strict_templates_rejects_unknown_template_id(rules_dir_factory, templates_file_factory):
    templates = templates_file_factory([])  # empty registry
    rules_dir = rules_dir_factory({
        "p.json": [
            {
                "rule_id": "r1",
                "name": "R1",
                "product": "*",
                "conditions": {"always": True},
                "actions": {"include_documents": [{"template_id": "unknown_doc"}]},
            }
        ]
    })
    with pytest.raises(RuleValidationError, match="unknown template_id"):
        RuleEngine(rules_dir, templates, strict_templates=True)


def test_reload_picks_up_file_changes(rules_dir_factory):
    rules_dir = rules_dir_factory({
        "p.json": [
            {
                "rule_id": "r1",
                "name": "R1",
                "product": "*",
                "conditions": {"always": True},
                "actions": {"include_documents": [{"template_id": "doc_a"}]},
            }
        ]
    })
    engine = RuleEngine(rules_dir)
    assert len(engine.rules) == 1

    (rules_dir / "p2.json").write_text(
        '[{"rule_id": "r2", "name": "R2", "product": "*", "conditions": {"always": true}, "actions": {}}]',
        encoding="utf-8",
    )
    engine.reload()
    assert len(engine.rules) == 2
