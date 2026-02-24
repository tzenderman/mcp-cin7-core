"""Purchase order tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict, project_items

logger = logging.getLogger("cin7_core_server.resources.purchase_orders")


async def cin7_purchase_orders(
    limit: int = 100,
    cursor: str | None = None,
    search: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List purchase orders with pagination and optional search filter.

    Returns summarized purchase order data with key fields by default.
    Use 'fields' parameter to request additional fields beyond the defaults.

    Parameters:
    - limit: Items per page (Cin7 limits apply)
    - cursor: Opaque cursor for next page (pass from previous response)
    - search: Optional search term
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: TaskID, Supplier, Status, OrderDate, Location, Order,
        RequiredBy, InvoiceDate, Total, Tax
        Default returns: TaskID, Supplier, Status, OrderDate, Location

    Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/get
    """
    logger.debug(
        "Tool call: cin7_purchase_orders(limit=%s, cursor=%s, search=%s)",
        limit, cursor, search,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_purchase_orders(page=page, limit=limit, search=search)

    items = raw.get("PurchaseList", [])
    total = raw.get("Total", len(items))

    # Apply field projection
    base_fields = {"TaskID", "Supplier", "Status", "OrderDate", "Location"}
    items = project_items(items, fields, base_fields=base_fields)

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_purchase_orders -> %s", truncate(str(result)))
    return result


async def cin7_get_purchase_order(
    purchase_order_id: str,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get a single purchase order by ID.

    Returns the complete purchase order object.

    Parameters:
    - purchase_order_id: Purchase order task ID (required)
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: ID, TaskID, Supplier, Location, Status, OrderDate, Order,
        RequiredBy, Lines, AdditionalCharges, Invoices
        Default returns: TaskID, Supplier, Status
    """
    logger.debug(
        "Tool call: cin7_get_purchase_order(purchase_order_id=%s)",
        purchase_order_id,
    )
    client = Cin7Client.from_env()
    result = await client.get_purchase_order(purchase_order_id=purchase_order_id)

    # Apply field projection
    result = project_dict(result, fields, base_fields={"TaskID", "Supplier", "Status"})

    logger.debug("Tool result: cin7_get_purchase_order -> %s", truncate(str(result)))
    return result


async def cin7_create_purchase_order(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core purchase order via POST Purchase.

    ALWAYS read cin7://templates/purchase_order first to get the complete payload
    structure before calling this tool. The template shows all available fields
    and their expected formats.

    Required PO-level fields — the API will reject the request if any are missing:
    - Supplier or SupplierID (supplier name or UUID)
    - Location (warehouse location name)
    - Status (PO status: "DRAFT" or "AUTHORISED")
    - OrderDate (ISO date string, e.g. "2024-01-15")

    Required fields for each line item (if including Lines):
    - ProductID (GUID — retrieve with cin7_get_product)
    - SKU (product SKU)
    - Name (product name)
    - Quantity (minimum 1)
    - Price (unit price)
    - Tax (tax amount)
    - TaxRule (tax rule name, e.g. "Tax Exempt")
    - Total (line total: (Price x Quantity) - Discount + Tax)

    Example workflow:
    1. Always read cin7://templates/purchase_order first to get the complete structure
    2. Get supplier info with cin7_get_supplier to retrieve the SupplierID
    3. Get product details with cin7_get_product to retrieve ProductID, SKU, Name
    4. Fill in all required PO-level fields listed above
    5. Calculate Total for each line: (Price x Quantity) - Discount + Tax
    6. Submit with cin7_create_purchase_order()

    Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/post
    """
    logger.debug("Tool call: cin7_create_purchase_order(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.save_purchase_order(payload)
    logger.debug("Tool result: cin7_create_purchase_order -> %s", truncate(str(result)))
    return result
