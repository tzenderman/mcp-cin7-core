"""Product tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_items

logger = logging.getLogger("cin7_core_server.resources.products")


async def cin7_products(
    page: int = 1,
    limit: int = 100,
    name: str | None = None,
    sku: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """List products with pagination and optional name/SKU filters.

    Parameters:
    - page: Page number (1-based)
    - limit: Items per page (Cin7 limits apply)
    - name: Optional name filter
    - sku: Optional SKU filter
    - fields: Optional list of additional field names to include per product
    """
    logger.debug(
        "Tool call: cin7_products(page=%s, limit=%s, name=%s, sku=%s)",
        page, limit, name, sku,
    )
    client = Cin7Client.from_env()
    result = await client.list_products(page=page, limit=limit, name=name, sku=sku)

    try:
        base_fields = {"SKU", "Name"}
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
            products = result.get("Products")
            if isinstance(products, list):
                result["Products"] = _project_list(products)
            elif isinstance(result.get("result"), list):
                result["result"] = _project_list(result["result"])
    except Exception:
        pass

    logger.debug("Tool result: cin7_products -> %s", truncate(str(result)))
    return result


async def cin7_get_product(
    product_id: str | None = None,
    sku: str | None = None,
) -> Dict[str, Any]:
    """Get a single product by ID or SKU.

    Returns the first matching product object.
    """
    logger.debug(
        "Tool call: cin7_get_product(product_id=%s, sku=%s)",
        product_id, sku,
    )
    client = Cin7Client.from_env()
    result = await client.get_product(product_id=product_id, sku=sku)
    logger.debug("Tool result: cin7_get_product -> %s", truncate(str(result)))
    return result


async def cin7_create_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core product via POST Product.

    Provide the JSON payload as defined by Cin7 Core API. The payload should follow
    the same structure as returned by cin7_product_template. This tool forwards
    the payload to POST Product and returns the API response including the
    newly created product with its assigned ID.

    Use cin7_product_template() to get a template with all available fields.
    Required fields typically include: SKU, Name, and Category.

    If a Suppliers array is provided, it will be automatically registered via
    the ProductSuppliers endpoint after product creation.

    Example workflow:
    1. Call cin7_product_template() to get the structure
    2. Fill in required fields (SKU, Name, Category) and any optional fields
    3. Optionally include Suppliers array with supplier associations
    4. Pass the completed payload to cin7_create_product()

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
