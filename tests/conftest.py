from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SAMPLE_RULES_DIR = REPO_ROOT / "rules" / "products"
SAMPLE_TEMPLATES_FILE = REPO_ROOT / "rules" / "documents" / "templates.json"


@pytest.fixture
def sample_rules_dir() -> Path:
    """The repo's real rules/products directory (mortgage.json, auto_loan.json)."""
    return SAMPLE_RULES_DIR


@pytest.fixture
def sample_templates_file() -> Path:
    return SAMPLE_TEMPLATES_FILE


@pytest.fixture
def rules_dir_factory(tmp_path):
    """Write a set of rule dicts/lists to a fresh temp rules directory and return its path.

    Usage: rules_dir_factory({"mortgage.json": [rule_dict, ...]})
    """

    def _make(files: dict[str, object]) -> Path:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        for filename, content in files.items():
            (rules_dir / filename).write_text(json.dumps(content), encoding="utf-8")
        return rules_dir

    return _make


@pytest.fixture
def templates_file_factory(tmp_path):
    def _make(templates: list[dict]) -> Path:
        path = tmp_path / "templates.json"
        path.write_text(json.dumps(templates), encoding="utf-8")
        return path

    return _make
