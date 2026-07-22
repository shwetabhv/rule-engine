"""RuleEngine: orchestrates loading + evaluation, resolving the final set of
documents to generate for a given product + client/account context."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from .exceptions import RuleValidationError
from .loader import RuleLoader
from .models import EvaluationResult, ResolvedDocument, Rule, RuleTraceEntry, TemplateDef

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(
        self,
        rules_dir: str | Path,
        templates_file: str | Path | None = None,
        strict_templates: bool = False,
    ):
        self._loader = RuleLoader(rules_dir, templates_file)
        self._strict_templates = strict_templates
        self._rules: list[Rule] = []
        self._templates: dict[str, TemplateDef] = {}
        self.reload()

    def reload(self) -> None:
        """Re-read all rule/template JSON files from disk. Call this after editing
        rule files to pick up changes without restarting the process."""
        rules = self._loader.load_rules()
        templates = self._loader.load_templates()
        if self._strict_templates and self._loader.templates_file is not None:
            self._validate_template_refs(rules, templates)
        self._rules = sorted(rules, key=lambda r: r.priority)
        self._templates = templates
        logger.info("Loaded %d rule(s), %d template(s)", len(self._rules), len(self._templates))

    @staticmethod
    def _validate_template_refs(rules: list[Rule], templates: dict[str, TemplateDef]) -> None:
        missing = sorted(
            (rule.rule_id, action.template_id)
            for rule in rules
            for action in rule.actions.include_documents
            if action.template_id not in templates
        )
        if missing:
            details = ", ".join(f"{rid} -> {tid}" for rid, tid in missing)
            raise RuleValidationError(f"Rules reference unknown template_id(s): {details}")

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    @property
    def templates(self) -> dict[str, TemplateDef]:
        return dict(self._templates)

    def get_rule(self, rule_id: str) -> Rule | None:
        return next((r for r in self._rules if r.rule_id == rule_id), None)

    def evaluate(self, product: str, context: dict[str, Any], as_of: date | None = None) -> EvaluationResult:
        """Resolve the final document set for a product given a client/account context.

        Rules are evaluated in ascending priority order (lower number = higher
        precedence). If two matching rules include the same template_id, or
        set the same variable, the first (highest-precedence) one encountered
        wins and the conflict is logged. Exclusions always win regardless of
        which rule's priority added the template - they're a deny mechanism,
        not a competing precedence tier.
        """
        as_of = as_of or date.today()

        resolved: dict[str, tuple[Any, str]] = {}
        excluded: set[str] = set()
        variables: dict[str, Any] = {}
        trace: list[RuleTraceEntry] = []
        matched_ids: list[str] = []

        for rule in self._rules:
            applies = rule.applies_to_product(product)
            active = rule.is_active
            effective = rule.is_effective(as_of)
            matched = applies and active and effective and rule.matches(context)

            trace.append(
                RuleTraceEntry(rule_id=rule.rule_id, name=rule.name, matched=matched, active=active, effective=effective)
            )
            if not matched:
                continue

            matched_ids.append(rule.rule_id)
            for inc in rule.actions.include_documents:
                if inc.template_id in resolved:
                    logger.warning(
                        "Template '%s' already included by higher-precedence rule '%s'; "
                        "ignoring conflicting include from rule '%s'",
                        inc.template_id,
                        resolved[inc.template_id][1],
                        rule.rule_id,
                    )
                    continue
                resolved[inc.template_id] = (inc, rule.rule_id)
            excluded.update(rule.actions.exclude_documents)
            for key, value in rule.actions.set_variables.items():
                # Same precedence rule as includes: first (highest-precedence) rule
                # to set a variable wins; lower-precedence rules can't clobber it.
                if key not in variables:
                    variables[key] = value

        documents = []
        for template_id, (action, rule_id) in resolved.items():
            if template_id in excluded:
                continue
            tmpl = self._templates.get(template_id)
            documents.append(
                ResolvedDocument(
                    template_id=template_id,
                    name=tmpl.name if tmpl else None,
                    file=tmpl.file if tmpl else None,
                    language=action.language or (tmpl.language if tmpl else None),
                    variables={**variables, **action.variables},
                    matched_rule_id=rule_id,
                )
            )

        return EvaluationResult(
            product=product,
            documents=documents,
            variables=variables,
            matched_rule_ids=matched_ids,
            trace=trace,
        )
