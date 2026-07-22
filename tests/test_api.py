from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client(sample_rules_dir, sample_templates_file):
    app = create_app(str(sample_rules_dir), str(sample_templates_file))
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["rules_loaded"] > 0


def test_list_rules(client):
    resp = client.get("/rules")
    assert resp.status_code == 200
    rule_ids = {r["rule_id"] for r in resp.json()}
    assert "mortgage_base_docs" in rule_ids


def test_list_rules_filtered_by_product(client):
    resp = client.get("/rules", params={"product": "auto_loan"})
    assert resp.status_code == 200
    rule_ids = {r["rule_id"] for r in resp.json()}
    assert "mortgage_base_docs" not in rule_ids
    assert "auto_loan_base_docs" in rule_ids


def test_get_rule_not_found(client):
    resp = client.get("/rules/does_not_exist")
    assert resp.status_code == 404


def test_get_rule(client):
    resp = client.get("/rules/mortgage_base_docs")
    assert resp.status_code == 200
    assert resp.json()["rule_id"] == "mortgage_base_docs"


def test_reload(client):
    resp = client.post("/rules/reload")
    assert resp.status_code == 200
    assert resp.json()["status"] == "reloaded"


def test_evaluate(client):
    resp = client.post("/evaluate", json={"product": "mortgage", "context": {"account": {"country": "DE"}}})
    assert resp.status_code == 200
    body = resp.json()
    ids = {d["template_id"] for d in body["documents"]}
    assert "mortgage_contract_de" in ids
    assert "mortgage_contract_en" not in ids


def test_evaluate_with_as_of_date(client):
    resp = client.post(
        "/evaluate",
        json={"product": "auto_loan", "context": {}, "as_of": "2026-03-01"},
    )
    assert resp.status_code == 200
    body = resp.json()
    kyc = next(d for d in body["documents"] if d["template_id"] == "kyc_form_en")
    assert kyc["variables"].get("note") == "regulatory_disclosure_v2026"
