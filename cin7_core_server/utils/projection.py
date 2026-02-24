"""Shared field projection helpers for MCP tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def project_dict(
    data: dict[str, Any],
    fields: list[str] | None,
    base_fields: set[str],
) -> dict[str, Any]:
    """Project a single dict to base_fields + requested fields.

    - fields=None: returns only base_fields (minimal default)
    - fields=["x"]: returns base_fields + x
    - fields=["*"]: returns full data (no projection)
    """
    if fields is not None and "*" in fields:
        return data

    allowed = base_fields | set(fields or [])
    return {k: v for k, v in data.items() if k in allowed}


def project_items(items: List[Dict[str, Any]], fields: Optional[List[str]], base_fields: set[str] | None = None) -> List[Dict[str, Any]]:
    """Project a list of dicts to only include base fields + requested fields.

    Args:
        items: List of dicts to project.
        fields: Additional field names to include beyond base_fields.
        base_fields: Base fields always included. Defaults to {"SKU", "Name"}.
    """
    if base_fields is None:
        base_fields = {"SKU", "Name"}
    if fields is not None and "*" in fields:
        return items
    requested_fields = set(fields or [])
    allowed = base_fields | requested_fields
    projected: List[Dict[str, Any]] = []
    for it in items:
        if isinstance(it, dict):
            projected.append({k: v for k, v in it.items() if k in allowed})
        else:
            projected.append(it)
    return projected


def project_stock_items(items: List[Dict[str, Any]], fields: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Project stock availability items to requested fields."""
    return project_items(items, fields, base_fields={"SKU", "Location", "OnHand", "Available"})


def project_list(items: list[dict[str, Any]], allowed_fields: set[str]) -> list[dict[str, Any]]:
    """Project a list of dicts to only include the specified allowed fields."""
    projected: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            projected.append({k: v for k, v in item.items() if k in allowed_fields})
        else:
            projected.append(item)
    return projected
