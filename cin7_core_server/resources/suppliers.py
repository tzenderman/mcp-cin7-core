"""Supplier tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict, project_items

logger = logging.getLogger("cin7_core_server.resources.suppliers")


async def cin7_suppliers(
    limit: int = 100,
    cursor: str | None = None,
    name: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List suppliers with pagination and optional name filter.

    Parameters:
    - limit: Items per page (Cin7 limits apply)
    - cursor: Opaque cursor for next page (pass from previous response)
    - name: Optional name filter
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: ID, Name, ContactPerson, Phone, Email, Currency, TaxRule, PaymentTerm
        Default returns: ID, Name
    """
    logger.debug(
        "Tool call: cin7_suppliers(limit=%s, cursor=%s, name=%s)",
        limit, cursor, name,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_suppliers(page=page, limit=limit, name=name)

    items = raw.get("SupplierList", [])
    total = raw.get("Total", len(items))

    # Apply field projection
    base_fields = {"ID", "Name"}
    items = project_items(items, fields, base_fields=base_fields)

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_suppliers -> %s", truncate(str(result)))
    return result


async def cin7_get_supplier(
    supplier_id: str | None = None,
    name: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get a single supplier by ID or name.

    Returns the first matching supplier object.

    Parameters:
    - supplier_id: Supplier GUID
    - name: Supplier name
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: ID, Name, ContactPerson, Phone, Email, Currency, TaxRule, PaymentTerm
        Default returns: ID, Name
    """
    logger.debug(
        "Tool call: cin7_get_supplier(supplier_id=%s, name=%s)",
        supplier_id, name,
    )
    client = Cin7Client.from_env()
    result = await client.get_supplier(supplier_id=supplier_id, name=name)

    # Apply field projection
    result = project_dict(result, fields, base_fields={"ID", "Name"})

    logger.debug("Tool result: cin7_get_supplier -> %s", truncate(str(result)))
    return result


async def cin7_create_supplier(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core supplier via POST Supplier.

    ALWAYS call cin7_supplier_template() first to get the complete payload structure
    before calling this tool. The template shows all available fields and their
    expected formats.

    Required fields — the API will reject the request if any of these are missing:
    - Name (supplier company name)
    - Currency (currency code, e.g. "USD", "AUD", "GBP")
    - PaymentTerm (e.g. "30 days", "COD", "Net 60")
    - AccountPayable (accounts payable account code from your chart of accounts)
    - TaxRule (e.g. "Tax Exempt", "GST on Income")

    Example workflow:
    1. Always call cin7_supplier_template() first to get the complete structure
    2. Fill in all required fields listed above
    3. Fill in any optional fields (ContactPerson, Phone, Email, Address, etc.)
    4. Pass the completed payload to cin7_create_supplier()

    Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/post
    """
    logger.debug("Tool call: cin7_create_supplier(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.save_supplier(payload)
    logger.debug("Tool result: cin7_create_supplier -> %s", truncate(str(result)))
    return result


async def cin7_update_supplier(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core supplier via PUT Supplier.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Supplier and returns the API response.

    Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/put
    """
    logger.debug("Tool call: cin7_update_supplier(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.update_supplier(payload)
    logger.debug("Tool result: cin7_update_supplier -> %s", truncate(str(result)))
    return result
