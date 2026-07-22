"""Validate rule/template JSON files without starting the API.

Usage:
    python scripts/validate_rules.py
    python scripts/validate_rules.py --rules-dir rules/products --templates-file rules/documents/templates.json

Intended for rule authors editing JSON by hand, and for CI to catch a bad
rule file before it's deployed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.engine import RuleEngine  # noqa: E402
from engine.exceptions import RuleEngineError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", default="rules/products")
    parser.add_argument("--templates-file", default="rules/documents/templates.json")
    parser.add_argument(
        "--no-strict-templates",
        action="store_true",
        help="Don't fail if a rule references a template_id missing from the templates file.",
    )
    args = parser.parse_args()

    try:
        eng = RuleEngine(args.rules_dir, args.templates_file, strict_templates=not args.no_strict_templates)
    except RuleEngineError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: {len(eng.rules)} rule(s) loaded, {len(eng.templates)} template(s) loaded")
    for rule in eng.rules:
        print(f"  [{rule.priority:>4}] {rule.rule_id:<40} product={rule.product} active={rule.is_active}")


if __name__ == "__main__":
    main()
