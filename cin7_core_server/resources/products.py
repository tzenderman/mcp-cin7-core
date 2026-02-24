"""Product tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict, project_items

logger = logging.getLogger("cin7_core_server.resources.products")


async def cin7_products(
    limit: int = 100,
    cursor: str | None = None,
    name: str | None = None,
    sku: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List products with pagination and optional name/SKU filters.

    Parameters:
    - limit: Items per page (Cin7 limits apply)
    - cursor: Opaque cursor for next page (pass from previous response)
    - name: Optional name filter
    - sku: Optional SKU filter
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: ID, SKU, Name, Category, Brand, Status, Type, UOM,
        CostingMethod, DefaultLocation, PriceTier1, PurchasePrice, Barcode
        Default returns: SKU, Name
    """
    logger.debug(
        "Tool call: cin7_products(limit=%s, cursor=%s, name=%s, sku=%s)",
        limit, cursor, name, sku,
    )
    page = int(cursor) if cursor else 1
    client = Cin7Client.from_env()
    raw = await client.list_products(page=page, limit=limit, name=name, sku=sku)

    items = raw.get("Products", [])
    total = raw.get("Total", len(items))

    # Apply field projection
    base_fields = {"SKU", "Name"}
    items = project_items(items, fields, base_fields=base_fields)

    has_more = (page * limit) < total
    result = {
        "results": items,
        "has_more": has_more,
        "cursor": str(page + 1) if has_more else None,
        "total_returned": len(items),
    }
    logger.debug("Tool result: cin7_products -> %s", truncate(str(result)))
    return result


async def cin7_get_product(
    product_id: str | None = None,
    sku: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Get a single product by ID or SKU.

    Parameters:
    - product_id: Product GUID
    - sku: Product SKU
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Available fields: ID, SKU, Name, Category, Brand, Status, Type, UOM,
        CostingMethod, DefaultLocation, PriceTier1, PurchasePrice, Barcode
        Default returns: ID, SKU, Name
    """
    logger.debug(
        "Tool call: cin7_get_product(product_id=%s, sku=%s)",
        product_id, sku,
    )
    client = Cin7Client.from_env()
    result = await client.get_product(product_id=product_id, sku=sku)

    # Apply field projection
    result = project_dict(result, fields, base_fields={"ID", "SKU", "Name"})

    logger.debug("Tool result: cin7_get_product -> %s", truncate(str(result)))
    return result


async def cin7_create_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core product via POST Product.

    ALWAYS call cin7_product_template() first to get the complete payload structure
    before calling this tool. The template shows all available fields and their
    expected formats.

    Required fields — the API will reject the request if any of these are missing:
    - SKU (product stock-keeping unit, must be unique)
    - Name (product display name)
    - Category (product category name)
    - Type (product type: "Stock", "Service", "Non Inventory", or "Assembly")
    - CostingMethod (inventory costing: "FIFO", "FEFO", "AVCO", or "Consignment")
    - UOM (unit of measure, e.g. "Each", "Kg", "L")
    - Status ("Active" or "Deprecated")

    If a Suppliers array is provided, it will be automatically registered via
    the ProductSuppliers endpoint after product creation.

    Example workflow:
    1. Always call cin7_product_template() first to get the complete structure
    2. Fill in all required fields listed above
    3. Fill in any optional fields (DefaultLocation, PriceTier1, Barcode, etc.)
    4. Optionally include a Suppliers array with supplier associations
    5. Pass the completed payload to cin7_create_product()

    Docs: https://dearinventory.docs.apiary.io/#reference/product/product/post
    """
    logger.debug("Tool call: cin7_create_product(payload=%s)", truncate(str(payload)))

    suppliers = None
    product_payload = dict(payload)
    if "Suppliers" in product_payload:
        suppliers = product_payload.pop("Suppliers")
        logger.debug("Extracted %d suppliers from payload for separate registration",
                    len(suppliers) if isinstance(suppliers, list) else 0)

    client = Cin7Client.from_env()
    result = await client.save_product(product_payload)
    logger.debug("Product created: %s", truncate(str(result)))

    if suppliers and isinstance(suppliers, list) and len(suppliers) > 0:
        product_id = None
        if isinstance(result, dict):
            product_id = result.get("ID") or result.get("ProductID")

        if product_id:
            logger.debug("Registering %d suppliers for product %s", len(suppliers), product_id)
            try:
                supplier_result = await client.update_product_suppliers([{
                    "ProductID": product_id,
                    "Suppliers": suppliers
                }])
                logger.debug("Suppliers registered: %s", truncate(str(supplier_result)))
                result["_suppliersRegistered"] = True
                result["_supplierCount"] = len(suppliers)
            except Exception as supplier_error:
                logger.error("Failed to register suppliers: %s", str(supplier_error))
                result["_suppliersRegistered"] = False
                result["_supplierError"] = str(supplier_error)
        else:
            logger.warning("Could not extract product ID from response to register suppliers")
            result["_suppliersRegistered"] = False
            result["_supplierError"] = "Could not extract product ID from response"

    logger.debug("Tool result: cin7_create_product -> %s", truncate(str(result)))
    return result


async def cin7_update_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core product via PUT Product.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Product and returns the API response.

    If a Suppliers array is provided, it will be automatically updated via
    the ProductSuppliers endpoint after product update.

    IMPORTANT: When updating suppliers, you must provide the FULL list of suppliers.
    Any suppliers not included in the array will be disassociated from the product.

    Docs: https://dearinventory.docs.apiary.io/#reference/product
    """
    logger.debug("Tool call: cin7_update_product(payload=%s)", truncate(str(payload)))

    suppliers = None
    product_payload = dict(payload)
    if "Suppliers" in product_payload:
        suppliers = product_payload.pop("Suppliers")
        logger.debug("Extracted %d suppliers from payload for separate update",
                    len(suppliers) if isinstance(suppliers, list) else 0)

    client = Cin7Client.from_env()
    result = await client.update_product(product_payload)
    logger.debug("Product updated: %s", truncate(str(result)))

    if suppliers and isinstance(suppliers, list) and len(suppliers) > 0:
        product_id = None
        if isinstance(product_payload, dict):
            product_id = product_payload.get("ID") or product_payload.get("ProductID")
        if not product_id and isinstance(result, dict):
            product_id = result.get("ID") or result.get("ProductID")

        if product_id:
            logger.debug("Updating %d suppliers for product %s", len(suppliers), product_id)
            try:
                supplier_result = await client.update_product_suppliers([{
                    "ProductID": product_id,
                    "Suppliers": suppliers
                }])
                logger.debug("Suppliers updated: %s", truncate(str(supplier_result)))
                result["_suppliersUpdated"] = True
                result["_supplierCount"] = len(suppliers)
            except Exception as supplier_error:
                logger.error("Failed to update suppliers: %s", str(supplier_error))
                result["_suppliersUpdated"] = False
                result["_supplierError"] = str(supplier_error)
        else:
            logger.warning("Could not extract product ID to update suppliers")
            result["_suppliersUpdated"] = False
            result["_supplierError"] = "Could not extract product ID from payload or response"

    logger.debug("Tool result: cin7_update_product -> %s", truncate(str(result)))
    return result
