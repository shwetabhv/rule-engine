"""FastAPI wrapper around RuleEngine.

Run with: uvicorn api.main:app --reload

Configuration is via environment variables so the same code can point at
different rule sets (e.g. a staging JSON directory) without edits:
  RULE_ENGINE_RULES_DIR        default "rules/products"
  RULE_ENGINE_TEMPLATES_FILE   default "rules/documents/templates.json"
  RULE_ENGINE_STRICT_TEMPLATES default "true"
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from engine.engine import RuleEngine
from engine.exceptions import RuleEngineError, RuleValidationError
from engine.models import EvaluationResult

from .schemas import EvaluateRequest


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes"}


def create_app(
    rules_dir: str | None = None,
    templates_file: str | None = None,
    strict_templates: bool | None = None,
) -> FastAPI:
    rules_dir = rules_dir or os.getenv("RULE_ENGINE_RULES_DIR", "rules/products")
    templates_file = templates_file or os.getenv("RULE_ENGINE_TEMPLATES_FILE", "rules/documents/templates.json")
    if strict_templates is None:
        strict_templates = _env_bool("RULE_ENGINE_STRICT_TEMPLATES", True)

    app = FastAPI(title="Document Rule Engine", version="0.1.0")
    app.state.engine = RuleEngine(rules_dir, templates_file, strict_templates=strict_templates)

    def get_engine(request: Request) -> RuleEngine:
        return request.app.state.engine

    @app.get("/health")
    def health(engine: RuleEngine = Depends(get_engine)) -> dict:
        return {"status": "ok", "rules_loaded": len(engine.rules), "templates_loaded": len(engine.templates)}

    @app.get("/rules")
    def list_rules(product: str | None = Query(None), engine: RuleEngine = Depends(get_engine)) -> list[dict]:
        rules = engine.rules
        if product:
            rules = [r for r in rules if r.applies_to_product(product)]
        return [r.model_dump(mode="json") for r in rules]

    @app.get("/rules/{rule_id}")
    def get_rule(rule_id: str, engine: RuleEngine = Depends(get_engine)) -> dict:
        rule = engine.get_rule(rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
        return rule.model_dump(mode="json")

    @app.post("/rules/reload")
    def reload_rules(engine: RuleEngine = Depends(get_engine)) -> dict:
        """Re-read rule/template JSON files from disk. Call after editing rules
        so changes take effect without restarting the process."""
        try:
            engine.reload()
        except RuleValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"status": "reloaded", "rules_loaded": len(engine.rules), "templates_loaded": len(engine.templates)}

    @app.post("/evaluate", response_model=EvaluationResult)
    def evaluate(req: EvaluateRequest, engine: RuleEngine = Depends(get_engine)) -> EvaluationResult:
        try:
            return engine.evaluate(req.product, req.context, req.as_of)
        except RuleEngineError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return app


app = create_app()
