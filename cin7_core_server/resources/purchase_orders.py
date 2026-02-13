"""Purchase order tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate

logger = logging.getLogger("cin7_core_server.resources.purchase_orders")


async def cin7_purchase_orders(
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List purchase orders with pagination and optional search filter.

    Returns summarized purchase order data with key fields by default.
    Use 'fields' parameter to request additional fields beyond the defaults.

    Parameters:
    - page: Page number (1-based)
    - limit: Items per page (Cin7 limits apply)
    - search: Optional search term
    - fields: Optional list of additional field names to include per purchase order

    Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/get
    """
    logger.debug(
        "Tool call: cin7_purchase_orders(page=%s, limit=%s, search=%s)",
        page, limit, search,
    )
    client = Cin7Client.from_env()
    result = await client.list_purchase_orders(page=page, limit=limit, search=search)

    try:
        base_fields = {"TaskID", "Supplier", "Status", "OrderDate", "Location"}
        requested_fields = set(fields or [])
        allowed_fields = base_fields | requested_fields

        def _project_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            projected: list[dict[str, Any]] = []
            for item in items:
                if isinstance(item, dict):
                    projected.append({k: v for k, v in item.items() if k in allowed_fields})
                else:
                    projected.append(item)
            return projected

        if isinstance(result, dict):
            purchases = result.get("PurchaseList")
            if isinstance(purchases, list):
                result["PurchaseList"] = _project_list(purchases)
            elif isinstance(result.get("result"), list):
                result["result"] = _project_list(result["result"])
    except Exception:
        pass

    logger.debug("Tool result: cin7_purchase_orders -> %s", truncate(str(result)))
    return result


async def cin7_get_purchase_order(
    purchase_order_id: str,
) -> Dict[str, Any]:
    """Get a single purchase order by ID.

    Returns the complete purchase order object.
    """
    logger.debug(
        "Tool call: cin7_get_purchase_order(purchase_order_id=%s)",
        purchase_order_id,
    )
    client = Cin7Client.from_env()
    result = await client.get_purchase_order(purchase_order_id=purchase_order_id)
    logger.debug("Tool result: cin7_get_purchase_order -> %s", truncate(str(result)))
    return result


async def cin7_create_purchase_order(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core purchase order via POST Purchase.

    Provide the JSON payload as defined by Cin7 Core API. The payload should follow
    the same structure as returned by the cin7://templates/purchase_order resource.

    IMPORTANT: All purchase orders are created with Status="DRAFT" to allow review
    before authorization. You can authorize the PO in the Cin7 Core web interface.

    Required PO-level fields:
    - Supplier (supplier name or ID)
    - Location (warehouse location)
    - OrderDate (YYYY-MM-DD format)
    - Lines (array with at least one line item)

    Required fields for each line item:
    - ProductID (GUID from cin7_get_product)
    - SKU (product SKU)
    - Name (product name)
    - Quantity (minimum 1)
    - Price (unit price)
    - Tax (tax amount)
    - TaxRule (tax rule name)
    - Total (line total: (Price x Quantity) - Discount + Tax)

    Example workflow:
    1. Read cin7://templates/purchase_order to get the complete structure
    2. Get product details with cin7_get_product to retrieve ProductID, SKU, Name
    3. Fill in all required PO-level and line-level fields
    4. Calculate Total for each line
    5. Pass the completed payload to cin7_create_purchase_order()
    6. The PO will be created as DRAFT status for user review

    Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/post
    """
    logger.debug("Tool call: cin7_create_purchase_order(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.save_purchase_order(payload)
    logger.debug("Tool result: cin7_create_purchase_order -> %s", truncate(str(result)))
    return result
