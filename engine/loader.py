"""Reads rule/template JSON files from disk. This is the only place that
touches the filesystem - swapping JSON files for a database later means
replacing this module, nothing else in the engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evaluator import validate_condition_tree
from .exceptions import RuleValidationError
from .models import Rule, TemplateDef


class RuleLoader:
    def __init__(self, rules_dir: str | Path, templates_file: str | Path | None = None):
        self.rules_dir = Path(rules_dir)
        self.templates_file = Path(templates_file) if templates_file else None

    def load_rules(self) -> list[Rule]:
        if not self.rules_dir.exists():
            raise RuleValidationError(f"Rules directory not found: {self.rules_dir}")

        rules: list[Rule] = []
        seen_ids: dict[str, str] = {}

        for path in sorted(self.rules_dir.glob("*.json")):
            data = self._read_json(path)
            entries = data if isinstance(data, list) else [data]
            for i, entry in enumerate(entries):
                entry = dict(entry)
                entry.pop("$schema", None)
                location = f"{path.name}[{i}]"
                try:
                    validate_condition_tree(entry.get("conditions", {}), path=f"{location}:conditions")
                    rule = Rule(**entry, source_file=str(path))
                except RuleValidationError:
                    raise
                except Exception as e:  # pydantic ValidationError etc.
                    raise RuleValidationError(f"Invalid rule at {location}: {e}") from e

                if rule.rule_id in seen_ids:
                    raise RuleValidationError(
                        f"Duplicate rule_id '{rule.rule_id}' in {path.name} "
                        f"(already defined in {seen_ids[rule.rule_id]})"
                    )
                seen_ids[rule.rule_id] = path.name
                rules.append(rule)

        return rules

    def load_templates(self) -> dict[str, TemplateDef]:
        if not self.templates_file:
            return {}
        if not self.templates_file.exists():
            raise RuleValidationError(f"Templates file not found: {self.templates_file}")

        data = self._read_json(self.templates_file)
        if not isinstance(data, list):
            raise RuleValidationError(f"{self.templates_file} must contain a JSON array of template definitions")

        templates: dict[str, TemplateDef] = {}
        for i, entry in enumerate(data):
            try:
                tmpl = TemplateDef(**entry)
            except Exception as e:
                raise RuleValidationError(f"Invalid template at {self.templates_file.name}[{i}]: {e}") from e
            if tmpl.template_id in templates:
                raise RuleValidationError(f"Duplicate template_id '{tmpl.template_id}' in {self.templates_file.name}")
            templates[tmpl.template_id] = tmpl

        return templates

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise RuleValidationError(f"Malformed JSON in {path}: {e}") from e
