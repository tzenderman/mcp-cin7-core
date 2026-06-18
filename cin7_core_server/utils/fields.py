"""Reusable field-list type for MCP tool parameters.

MCP clients may serialize ``list[str]`` values as JSON-encoded strings
(e.g. ``'["PriceTier1"]'``) when the JSON Schema omits ``type: array``.
``FieldList`` is an ``Annotated`` type that:

1. Emits correct JSON Schema (``type: array, items: {type: string}``).
2. Coerces incoming strings to ``list[str]`` at runtime so both forms work.
"""

from __future__ import annotations

import json
from typing import Annotated, List, Optional

from pydantic import BeforeValidator


def _coerce_field_list(v: object) -> Optional[List[str]]:
    """Normalize *v* to ``list[str] | None``."""
    if v is None:
        return None
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        stripped = v.strip()
        if not stripped:
            return None
        # Try JSON first: '["a","b"]'
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (json.JSONDecodeError, ValueError):
                pass
        # Fall back to comma-separated: 'a,b,c'
        return [s.strip() for s in stripped.split(",") if s.strip()]
    return v  # type: ignore[return-value]  # let pydantic raise


FieldList = Annotated[list[str] | None, BeforeValidator(_coerce_field_list)]
