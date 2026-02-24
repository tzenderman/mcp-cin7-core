"""Stock availability and stock transfer tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict, project_items, project_stock_items

logger = logging.getLogger("cin7_core_server.resources.stock")


async def cin7_stock_levels(
    limit: int = 100,
    cursor: str | None = None,
    location: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List stock levels across all products and locations.

    Default fields: SKU, Location, OnHand, Available
    Optional fields: Allocated, OnOrder, InTransit, NextDeliveryDate, Bin, Batch, Barcode

    Parameters:
    - limit: Items per page (max 1000)
    - cursor: Opaque cursor for next page (pass from previous response)
    - location: Filter by location name
    - fields: Additional fields beyond defaults, or ["*"] for all

    Available fields: SKU, Location, OnHand, Available, Allocated, OnOrder,
        InTransit, NextDeliveryDate, Bin, Batch, Barcode
        Default returns: SKU, Location, OnHand, Available
    """
    logger.debug(
        "Tool call: cin7_stock_levels(limit=%s, cursor=%s, location=%s, fields=%s)",
        limit, cursor, location, fields,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_product_availability(
        page=page, limit=limit, location=location
    )

    items = raw.get("ProductAvailabilityList", [])
    total = raw.get("Total", len(items))

    # Apply field projection
    items = project_stock_items(items, fields)

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_stock_levels -> %s", truncate(str(result)))
    return result


async def cin7_get_stock(
    sku: str | None = None,
    product_id: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get stock levels for a single product across all locations.

    Parameters:
    - sku: Product SKU (preferred)
    - product_id: Product GUID
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: sku, product_id, locations, total_on_hand, total_available
        Default returns: sku, product_id
    """
    logger.debug(
        "Tool call: cin7_get_stock(sku=%s, product_id=%s)",
        sku, product_id,
    )
    client = Cin7Client.from_env()
    locations = await client.get_product_availability(
        sku=sku, product_id=product_id
    )

    total_on_hand = sum(loc.get("OnHand", 0) or 0 for loc in locations)
    total_available = sum(loc.get("Available", 0) or 0 for loc in locations)

    result_sku = sku
    if not result_sku and locations:
        result_sku = locations[0].get("SKU", "")

    result = {
        "sku": result_sku,
        "product_id": product_id or (locations[0].get("ProductID") if locations else None),
        "locations": locations,
        "total_on_hand": total_on_hand,
        "total_available": total_available,
    }

    # Apply field projection
    result = project_dict(result, fields, base_fields={"sku", "product_id"})

    logger.debug("Tool result: cin7_get_stock -> %s", truncate(str(result)))
    return result


async def cin7_stock_transfers(
    limit: int = 100,
    cursor: str | None = None,
    search: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List stock transfers with pagination and optional search filter.

    Returns summarized stock transfer data with key fields by default.
    Use 'fields' parameter to request additional fields beyond the defaults.

    Parameters:
    - limit: Items per page (Cin7 limits apply)
    - cursor: Opaque cursor for next page (pass from previous response)
    - search: Optional search term
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: TaskID, FromLocation, ToLocation, Status, TransferDate, Lines
        Default returns: TaskID, FromLocation, ToLocation, Status, TransferDate

    Docs: https://dearinventory.docs.apiary.io/#reference/stock/stock-transfer-list
    """
    logger.debug(
        "Tool call: cin7_stock_transfers(limit=%s, cursor=%s, search=%s)",
        limit, cursor, search,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_stock_transfers(page=page, limit=limit, search=search)

    items = raw.get("StockTransferList", [])
    total = raw.get("Total", len(items))

    # Apply field projection
    base_fields = {"TaskID", "FromLocation", "ToLocation", "Status", "TransferDate"}
    items = project_items(items, fields, base_fields=base_fields)

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_stock_transfers -> %s", truncate(str(result)))
    return result


async def cin7_get_stock_transfer(
    stock_transfer_id: str,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get a single stock transfer by ID.

    Returns the complete stock transfer object.

    Parameters:
    - stock_transfer_id: Stock transfer task ID (required)
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: TaskID, FromLocation, ToLocation, Status, TransferDate, Lines
        Default returns: TaskID, FromLocation, ToLocation

    Docs: https://dearinventory.docs.apiary.io/#reference/stock/stock-transfer
    """
    logger.debug(
        "Tool call: cin7_get_stock_transfer(stock_transfer_id=%s)",
        stock_transfer_id,
    )
    client = Cin7Client.from_env()
    result = await client.get_stock_transfer(stock_transfer_id=stock_transfer_id)

    # Apply field projection
    result = project_dict(result, fields, base_fields={"TaskID", "FromLocation", "ToLocation"})

    logger.debug("Tool result: cin7_get_stock_transfer -> %s", truncate(str(result)))
    return result
