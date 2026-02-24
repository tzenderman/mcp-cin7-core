"""Sale tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict, project_items

logger = logging.getLogger("cin7_core_server.resources.sales")


async def cin7_sales(
    limit: int = 100,
    cursor: str | None = None,
    search: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List sales with pagination and optional search filter.

    Returns summarized sale data with only key fields by default:
    - Order (sale order ID)
    - SaleOrderNumber (reference)
    - Customer (customer name)
    - Location (sales channel/location)

    Use 'fields' parameter to request additional fields beyond the defaults.

    Parameters:
    - limit: Items per page (Cin7 limits apply)
    - cursor: Opaque cursor for next page (pass from previous response)
    - search: Optional search term
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: Order, SaleOrderNumber, Customer, Location, Status, OrderDate,
        InvoiceDate, Total, Tax, TotalPaid
        Default returns: Order, SaleOrderNumber, Customer, Location

    Docs: https://dearinventory.docs.apiary.io/#reference/sale/sale-list/get
    """
    logger.debug(
        "Tool call: cin7_sales(limit=%s, cursor=%s, search=%s)",
        limit, cursor, search,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_sales(page=page, limit=limit, search=search)

    items = raw.get("SaleList", [])
    total = raw.get("Total", len(items))

    # Apply field projection
    base_fields = {"Order", "SaleOrderNumber", "Customer", "Location"}
    items = project_items(items, fields, base_fields=base_fields)

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_sales -> %s", truncate(str(result)))
    return result


async def cin7_get_sale(
    sale_id: str,
    combine_additional_charges: bool = False,
    hide_inventory_movements: bool = False,
    include_transactions: bool = False,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get a single sale by ID with full details including line items.

    Returns complete sale data including:
    - Quote: Quote stage with lines and additional charges
    - Order: Order stage with SaleOrderNumber, lines, and additional charges
    - Fulfilments: Pick, Pack, Ship details with line items
    - Invoices: Invoice details with lines and payments
    - CreditNotes: Credit note details if any
    - InventoryMovements: Stock movements (unless hidden)
    - Transactions: Financial transactions (if requested)

    Parameters:
    - sale_id: The sale UUID (required)
    - combine_additional_charges: Combine additional charges into line totals
    - hide_inventory_movements: Exclude inventory movement details from response
    - include_transactions: Include financial transaction details
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: ID, Order, Customer, Location, Status, Quote, Order, Fulfilments,
        Invoices, CreditNotes, InventoryMovements, Transactions
        Default returns: ID, Order, Customer

    Docs: https://dearinventory.docs.apiary.io/#reference/sale/sale/get
    """
    logger.debug(
        "Tool call: cin7_get_sale(sale_id=%s, combine_additional_charges=%s, "
        "hide_inventory_movements=%s, include_transactions=%s)",
        sale_id, combine_additional_charges, hide_inventory_movements, include_transactions,
    )
    client = Cin7Client.from_env()
    result = await client.get_sale(
        sale_id=sale_id,
        combine_additional_charges=combine_additional_charges,
        hide_inventory_movements=hide_inventory_movements,
        include_transactions=include_transactions,
    )

    # Apply field projection
    result = project_dict(result, fields, base_fields={"ID", "Order", "Customer"})

    logger.debug("Tool result: cin7_get_sale -> %s", truncate(str(result)))
    return result


async def cin7_create_sale(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core sale via POST Sale.

    ALWAYS read cin7://templates/sale first to get the complete payload structure
    before calling this tool. The template shows all available fields and their
    expected formats.

    Required fields — the API will reject the request if any of these are missing:
    - Customer or CustomerID (customer name or UUID)
    - Location (warehouse/sales location name)
    - Status (sale status: "DRAFT" or "AUTHORISED")
    - SkipQuote (boolean: true = go directly to Order stage, false = create Quote first)

    Required fields for each line item (if including Lines):
    - ProductID (GUID — retrieve with cin7_get_product)
    - SKU (product SKU)
    - Name (product name)
    - Quantity (minimum 1)
    - Price (unit price)
    - Tax (tax amount)
    - TaxRule (tax rule name, e.g. "Tax Exempt")
    - Total (line total: (Price x Quantity) - Discount + Tax)

    Optional but commonly used fields:
    - Lines (array of line items — forwarded internally to POST /sale/order)
    - BillingAddress, ShippingAddress
    - TaxRule (sale-level default tax rule)
    - Terms (payment terms, e.g. "30 days")
    - PriceTier (e.g. "Tier 1")
    - SaleOrderDate (ISO date string, defaults to today)

    Example workflow:
    1. Always read cin7://templates/sale first to get the complete structure
    2. Get product info with cin7_get_product to retrieve ProductID, SKU, Name
    3. Fill in all required fields listed above
    4. Calculate Total for each line: (Price x Quantity) - Discount + Tax
    5. Submit with cin7_create_sale()

    Docs: https://dearinventory.docs.apiary.io/#reference/sale/sale/post
    """
    logger.debug("Tool call: cin7_create_sale(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.save_sale(payload)
    logger.debug("Tool result: cin7_create_sale -> %s", truncate(str(result)))
    return result


async def cin7_update_sale(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core sale via PUT Sale.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Sale and returns the API response.

    The payload must include the SaleID of the sale to update.

    Docs: https://dearinventory.docs.apiary.io/#reference/sale/sale/put
    """
    logger.debug("Tool call: cin7_update_sale(payload=%s)", truncate(str(payload)))
    client = Cin7Client.from_env()
    result = await client.update_sale(payload)
    logger.debug("Tool result: cin7_update_sale -> %s", truncate(str(result)))
    return result
