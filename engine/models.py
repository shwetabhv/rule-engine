from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentAction(BaseModel):
    """One template a matching rule contributes to the resolved document set."""

    template_id: str
    language: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class RuleActions(BaseModel):
    include_documents: list[DocumentAction] = Field(default_factory=list)
    exclude_documents: list[str] = Field(default_factory=list)
    set_variables: dict[str, Any] = Field(default_factory=dict)


class Rule(BaseModel):
    rule_id: str
    name: str
    description: str | None = None
    product: list[str]
    """List of product codes this rule applies to, or ["*"] for all products."""
    priority: int = 100
    """Lower number = evaluated with higher precedence when two rules include
    the same template_id with conflicting overrides. Default 100."""
    is_active: bool = True
    effective_from: date | None = None
    effective_to: date | None = None
    conditions: dict[str, Any]
    actions: RuleActions
    source_file: str | None = None
    """Populated by the loader; which JSON file this rule came from (for audit/debugging)."""

    @field_validator("product", mode="before")
    @classmethod
    def _normalize_product(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [v]
        return v

    def applies_to_product(self, product: str) -> bool:
        return "*" in self.product or product in self.product

    def is_effective(self, as_of: date) -> bool:
        if self.effective_from and as_of < self.effective_from:
            return False
        if self.effective_to and as_of > self.effective_to:
            return False
        return True

    def matches(self, context: dict[str, Any]) -> bool:
        from .evaluator import evaluate

        return evaluate(self.conditions, context)


class TemplateDef(BaseModel):
    template_id: str
    name: str
    file: str
    language: str | None = None
    description: str | None = None


class ResolvedDocument(BaseModel):
    template_id: str
    name: str | None = None
    file: str | None = None
    language: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    matched_rule_id: str


class RuleTraceEntry(BaseModel):
    rule_id: str
    name: str
    matched: bool
    active: bool
    effective: bool


class EvaluationResult(BaseModel):
    product: str
    documents: list[ResolvedDocument]
    variables: dict[str, Any]
    matched_rule_ids: list[str]
    trace: list[RuleTraceEntry]
