"""Supplier tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate

logger = logging.getLogger("cin7_core_server.resources.suppliers")


async def cin7_suppliers(
    page: int = 1,
    limit: int = 100,
    name: str | None = None,
) -> Dict[str, Any]:
    """List suppliers with pagination and optional name filter.

    Parameters:
    - page: Page number (1-based)
    - limit: Items per page (Cin7 limits apply)
    - name: Optional name filter
    """
    logger.debug(
        "Tool call: cin7_suppliers(page=%s, limit=%s, name=%s)",
        page, limit, name,
    )
    client = Cin7Client.from_env()
    result = await client.list_suppliers(page=page, limit=limit, name=name)
    logger.debug("Tool result: cin7_suppliers -> %s", truncate(str(result)))
    return result


async def cin7_get_supplier(
    supplier_id: str | None = None,
    name: str | None = None,
) -> Dict[str, Any]:
    """Get a single supplier by ID or name.

    Returns the first matching supplier object.
    """
    logger.debug(
        "Tool call: cin7_get_supplier(supplier_id=%s, name=%s)",
        supplier_id, name,
    )
    client = Cin7Client.from_env()
    result = await client.get_supplier(supplier_id=supplier_id, name=name)
    logger.debug("Tool result: cin7_get_supplier -> %s", truncate(str(result)))
    return result


async def cin7_create_supplier(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core supplier via POST Supplier.

    Provide the JSON payload as defined by Cin7 Core API. The payload should follow
    the same structure as returned by cin7_supplier_template. This tool forwards
    the payload to POST Supplier and returns the API response including the
    newly created supplier with its assigned ID.

    Use cin7_supplier_template() to get a template with all available fields.
    Required fields typically include: Name.

    Example workflow:
    1. Call cin7_supplier_template() to get the structure
    2. Fill in required fields (Name) and any optional fields
    3. Pass the completed payload to cin7_create_supplier()

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
