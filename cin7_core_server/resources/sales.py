"""Sale tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate

logger = logging.getLogger("cin7_core_server.resources.sales")


async def cin7_sales(
    page: int = 1,
    limit: int = 100,
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
    - page: Page number (1-based)
    - limit: Items per page (Cin7 limits apply)
    - search: Optional search term
    - fields: Optional list of additional field names to include per sale

    Docs: https://dearinventory.docs.apiary.io/#reference/sale/sale-list/get
    """
    logger.debug(
        "Tool call: cin7_sales(page=%s, limit=%s, search=%s)",
        page, limit, search,
    )
    client = Cin7Client.from_env()
    result = await client.list_sales(page=page, limit=limit, search=search)

    try:
        base_fields = {"Order", "SaleOrderNumber", "Customer", "Location"}
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
            sales = result.get("SaleList")
            if isinstance(sales, list):
                result["SaleList"] = _project_list(sales)
            elif isinstance(result.get("result"), list):
                result["result"] = _project_list(result["result"])
    except Exception:
        pass

    logger.debug("Tool result: cin7_sales -> %s", truncate(str(result)))
    return result


async def cin7_get_sale(
    sale_id: str,
    combine_additional_charges: bool = False,
    hide_inventory_movements: bool = False,
    include_transactions: bool = False,
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
    logger.debug("Tool result: cin7_get_sale -> %s", truncate(str(result)))
    return result


async def cin7_create_sale(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core sale via POST Sale.

    Provide the JSON payload as defined by Cin7 Core API. The payload should follow
    the same structure as returned by the cin7://templates/sale resource.

    IMPORTANT: All new sales are created with Status="DRAFT" by default to allow
    review before authorization. You can set Status="AUTHORISED" to create an
    authorized quote directly.

    Required fields:
    - Customer or CustomerID (customer name or ID)
    - Location (warehouse/sales location)
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

    Optional but recommended fields:
    - BillingAddress, ShippingAddress
    - TaxRule (sale-level default)
    - Terms (payment terms, e.g., "30 days")
    - PriceTier (e.g., "Tier 1")
    - SaleOrderDate (defaults to today)
    - SkipQuote (false = create Quote first, true = skip to Order)

    Example workflow:
    1. Read cin7://templates/sale to get the complete structure
    2. Get customer info with cin7_suppliers or use customer name
    3. Get product info with cin7_get_product (to get ProductID, SKU, Name)
    4. Calculate line totals: (Price x Quantity) - Discount + Tax
    5. Build Lines array with all required fields
    6. Submit with cin7_create_sale()
    7. Sale will be created as DRAFT Quote for user review

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
