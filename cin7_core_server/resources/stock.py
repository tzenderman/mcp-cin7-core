"""Stock availability and stock transfer tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_stock_items

logger = logging.getLogger("cin7_core_server.resources.stock")


async def cin7_stock_levels(
    page: int = 1,
    limit: int = 100,
    location: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List stock levels across all products and locations.

    Default fields: SKU, Location, OnHand, Available
    Optional fields: Allocated, OnOrder, InTransit, NextDeliveryDate, Bin, Batch, Barcode

    Parameters:
    - page: Page number (1-based)
    - limit: Items per page (max 1000)
    - location: Filter by location name
    - fields: Additional fields beyond defaults (e.g., ["Allocated", "OnOrder"])

    Returns:
        ProductAvailabilityList with stock data per SKU/location
    """
    logger.debug(
        "Tool call: cin7_stock_levels(page=%s, limit=%s, location=%s, fields=%s)",
        page, limit, location, fields,
    )
    client = Cin7Client.from_env()
    result = await client.list_product_availability(
        page=page, limit=limit, location=location
    )

    if isinstance(result, dict):
        items = result.get("ProductAvailabilityList")
        if isinstance(items, list):
            result["ProductAvailabilityList"] = project_stock_items(items, fields)

    logger.debug("Tool result: cin7_stock_levels -> %s", truncate(str(result)))
    return result


async def cin7_get_stock(
    sku: str | None = None,
    product_id: str | None = None,
) -> Dict[str, Any]:
    """Get stock levels for a single product across all locations.

    Parameters:
    - sku: Product SKU (preferred)
    - product_id: Product GUID

    Returns:
        Dict with:
        - sku: The product SKU
        - locations: List of location entries with OnHand, Available, Allocated, OnOrder
        - total_on_hand: Sum of OnHand across all locations
        - total_available: Sum of Available across all locations
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

    logger.debug("Tool result: cin7_get_stock -> %s", truncate(str(result)))
    return result


async def cin7_stock_transfers(
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List stock transfers with pagination and optional search filter.

    Returns summarized stock transfer data with key fields by default.
    Use 'fields' parameter to request additional fields beyond the defaults.

    Parameters:
    - page: Page number (1-based)
    - limit: Items per page (Cin7 limits apply)
    - search: Optional search term
    - fields: Optional list of additional field names to include per stock transfer

    Docs: https://dearinventory.docs.apiary.io/#reference/stock/stock-transfer-list
    """
    logger.debug(
        "Tool call: cin7_stock_transfers(page=%s, limit=%s, search=%s)",
        page, limit, search,
    )
    client = Cin7Client.from_env()
    result = await client.list_stock_transfers(page=page, limit=limit, search=search)

    try:
        base_fields = {"TaskID", "FromLocation", "ToLocation", "Status", "TransferDate"}
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
            stock_transfers = result.get("StockTransferList")
            if isinstance(stock_transfers, list):
                result["StockTransferList"] = _project_list(stock_transfers)
            elif isinstance(result.get("result"), list):
                result["result"] = _project_list(result["result"])
    except Exception:
        pass

    logger.debug("Tool result: cin7_stock_transfers -> %s", truncate(str(result)))
    return result


async def cin7_get_stock_transfer(
    stock_transfer_id: str,
) -> Dict[str, Any]:
    """Get a single stock transfer by ID.

    Returns the complete stock transfer object.

    Docs: https://dearinventory.docs.apiary.io/#reference/stock/stock-transfer
    """
    logger.debug(
        "Tool call: cin7_get_stock_transfer(stock_transfer_id=%s)",
        stock_transfer_id,
    )
    client = Cin7Client.from_env()
    result = await client.get_stock_transfer(stock_transfer_id=stock_transfer_id)
    logger.debug("Tool result: cin7_get_stock_transfer -> %s", truncate(str(result)))
    return result
