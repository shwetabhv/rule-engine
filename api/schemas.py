from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    product: str
    context: dict[str, Any]
    as_of: date | None = None
