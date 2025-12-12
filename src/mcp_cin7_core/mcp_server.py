from __future__ import annotations

from typing import Any, Dict
from pathlib import Path
import os
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import uuid
import time
import json
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from .cin7_client import Cin7Client, Cin7ClientError


# Load environment variables from .env using a robust search strategy.
# 1) Try current working directory (default behavior)
# 2) Fallback to project root inferred from this file location
loaded = load_dotenv()
if not loaded:
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO),
                    format="%(asctime)s %(name)s %(levelname)s: %(message)s")

_log_file = os.getenv("MCP_LOG_FILE")
if _log_file:
    try:
        handler = RotatingFileHandler(_log_file, maxBytes=5_000_000, backupCount=3)
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(handler)
    except Exception:
        # If file handler fails, continue with stdout logging only
        pass

logger = logging.getLogger("mcp_cin7_core.server")

def _truncate(text: str, max_len: int = 2000) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... [truncated]"


def create_mcp_server(auth=None):
    """Create and configure the FastMCP server with all tools, resources, and prompts.
    
    Args:
        auth: Optional auth provider (e.g., ScalekitProvider) for OAuth
    """
    server = FastMCP("mcp-cin7-core", auth=auth)
    
    # Register all tools
    server.tool()(cin7_status)
    server.tool()(cin7_me)
    server.tool()(cin7_products_snapshot_start)
    server.tool()(cin7_products_snapshot_chunk)
    server.tool()(cin7_products_snapshot_close)
    server.tool()(cin7_products)
    server.tool()(cin7_products_snapshot_status)
    server.tool()(cin7_get_product)
    server.tool()(cin7_create_product)
    server.tool()(cin7_update_product)
    server.tool()(cin7_suppliers)
    server.tool()(cin7_get_supplier)
    server.tool()(cin7_create_supplier)
    server.tool()(cin7_update_supplier)
    server.tool()(cin7_sales)
    server.tool()(cin7_purchase_orders)
    server.tool()(cin7_get_purchase_order)
    server.tool()(cin7_create_purchase_order)
    server.tool()(cin7_stock_transfers)
    server.tool()(cin7_get_stock_transfer)
    
    # Register all resources
    server.resource("cin7://templates/product")(resource_product_template)
    server.resource("cin7://templates/product/{product_id}")(resource_product_by_id)
    server.resource("cin7://templates/product/sku/{sku}")(resource_product_by_sku)
    server.resource("cin7://templates/supplier")(resource_supplier_template)
    server.resource("cin7://templates/supplier/{supplier_id}")(resource_supplier_by_id)
    server.resource("cin7://templates/supplier/name/{name}")(resource_supplier_by_name)
    server.resource("cin7://templates/purchase_order")(resource_purchase_order_template)
    server.resource("cin7://templates/purchase_order/{purchase_order_id}")(resource_purchase_order_by_id)
    
    # Register all prompts
    server.prompt()(create_product)
    server.prompt()(update_batch)
    server.prompt()(verify_required_fields)
    server.prompt()(create_purchase_order)
    
    return server
# ----------------------------- Snapshot storage -----------------------------

SNAPSHOT_TTL_SECONDS = 15 * 60
SNAPSHOT_MAX_ITEMS = 250_000

@dataclass
class ProductSnapshot:
    id: str
    created_at: float
    total: int = 0
    items: List[Dict[str, Any]] = field(default_factory=list)
    ready: bool = False
    error: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > SNAPSHOT_TTL_SECONDS


_snapshots: Dict[str, ProductSnapshot] = {}
_snapshot_tasks: Dict[str, asyncio.Task] = {}


def _cleanup_expired_snapshots() -> None:
    expired: List[str] = []
    now = time.time()
    for sid, snap in list(_snapshots.items()):
        if (now - snap.created_at) > SNAPSHOT_TTL_SECONDS:
            expired.append(sid)
    for sid in expired:
        _snapshots.pop(sid, None)
        task = _snapshot_tasks.pop(sid, None)
        if task and not task.done():
            task.cancel()


def _project_items(items: List[Dict[str, Any]], fields: Optional[List[str]]) -> List[Dict[str, Any]]:
    base_fields = {"SKU", "Name"}
    requested_fields = set(fields or [])
    allowed = base_fields | requested_fields
    projected: List[Dict[str, Any]] = []
    for it in items:
        if isinstance(it, dict):
            projected.append({k: v for k, v in it.items() if k in allowed})
        else:
            projected.append(it)
    return projected


async def _build_snapshot(sid: str, page: int, limit: int, name: Optional[str], sku: Optional[str], fields: Optional[List[str]]) -> None:
    client = Cin7Client.from_env()
    snap = _snapshots.get(sid)
    try:
        # First call to determine total pages; Cin7 API returns Products and maybe paging info.
        current_page = page
        per_page = limit
        while True:
            result = await client.list_products(page=current_page, limit=per_page, name=name, sku=sku)
            products = []
            if isinstance(result, dict):
                plist = result.get("Products")
                if isinstance(plist, list):
                    products = plist
                elif isinstance(result.get("result"), list):
                    products = result["result"]
            if not isinstance(products, list):
                products = []

            projected = _project_items(products, fields)

            # Guard against unbounded memory
            if snap is None:
                break
            if len(snap.items) + len(projected) > SNAPSHOT_MAX_ITEMS:
                snap.error = f"Snapshot item cap reached ({SNAPSHOT_MAX_ITEMS})."
                break
            snap.items.extend(projected)
            snap.total = len(snap.items)

            # Determine if more pages exist
            # Cin7 doesn't always provide total pages; loop until empty page
            if len(products) < per_page:
                break
            current_page += 1

        if snap is not None and not snap.error:
            snap.ready = True
    except Exception as exc:
        if snap is not None:
            snap.error = str(exc)
    finally:
        await client.aclose()



async def cin7_status() -> Dict[str, Any]:
    """Verify Cin7 Core credentials by fetching a minimal page of products."""
    logger.debug("Tool call: cin7_status()")
    client = Cin7Client.from_env()
    try:
        result = await client.health_check()
        logger.debug("Tool result: cin7_status() -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


async def cin7_me() -> Dict[str, Any]:
    """Call Cin7 Core Me endpoint to verify identity and account context."""
    logger.debug("Tool call: cin7_me()")
    client = Cin7Client.from_env()
    try:
        result = await client.get_me()
        logger.debug("Tool result: cin7_me() -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


async def cin7_products_snapshot_start(
    page: int = 1,
    limit: int = 100,
    name: str | None = None,
    sku: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Start a server-side snapshot build of products.

    Returns a snapshotId that can be used to fetch chunks, check status, or close.
    The snapshot applies default projection (SKU, Name) plus any requested fields.
    """
    _cleanup_expired_snapshots()

    sid = str(uuid.uuid4())
    snap = ProductSnapshot(
        id=sid,
        created_at=time.time(),
        total=0,
        items=[],
        ready=False,
        error=None,
        params={
            "page": page,
            "limit": limit,
            "name": name,
            "sku": sku,
            "fields": list(fields or []),
        },
    )
    _snapshots[sid] = snap

    task = asyncio.create_task(_build_snapshot(sid, page, limit, name, sku, fields))
    _snapshot_tasks[sid] = task

    return {
        "snapshotId": sid,
        "ready": snap.ready,
        "total": snap.total,
    }

async def cin7_products_snapshot_chunk(
    snapshot_id: str,
    offset: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch a slice of items from a built or building snapshot.

    If the snapshot is still building, this returns whatever is available.
    """
    _cleanup_expired_snapshots()
    snap = _snapshots.get(snapshot_id)
    if not snap:
        return {"error": "snapshot not found"}
    start = max(0, int(offset))
    end = max(start, start + int(limit))
    items = snap.items[start:end]
    next_offset = end if end < len(snap.items) else None
    return {
        "snapshotId": snap.id,
        "ready": snap.ready,
        "total": snap.total,
        "items": items,
        "nextOffset": next_offset,
    }

async def cin7_products_snapshot_close(snapshot_id: str) -> Dict[str, Any]:
    """Close and clean up a snapshot, cancelling work if still running."""
    snap = _snapshots.pop(snapshot_id, None)
    task = _snapshot_tasks.pop(snapshot_id, None)
    if task and not task.done():
        task.cancel()
    return {"ok": True, "snapshotId": snapshot_id, "existed": snap is not None}

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
        page,
        limit,
        name,
        sku,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_products(page=page, limit=limit, name=name, sku=sku)

        # Project returned products to only SKU, Name, and any explicitly requested fields
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
            # If projection fails for any reason, return the original result
            pass

        logger.debug("Tool result: cin7_products -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


async def cin7_products_snapshot_status(snapshot_id: str) -> Dict[str, Any]:
    """Get status and metadata for a running or completed snapshot."""
    _cleanup_expired_snapshots()
    snap = _snapshots.get(snapshot_id)
    if not snap:
        return {"error": "snapshot not found"}
    return {
        "snapshotId": snap.id,
        "ready": snap.ready,
        "total": snap.total,
        "error": snap.error,
        "params": snap.params,
    }

async def cin7_get_product(
    product_id: int | None = None,
    sku: str | None = None,
) -> Dict[str, Any]:
    """Get a single product by ID or SKU.

    Returns the first matching product object.
    """
    logger.debug(
        "Tool call: cin7_get_product(product_id=%s, sku=%s)",
        product_id,
        sku,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.get_product(product_id=product_id, sku=sku)
        logger.debug("Tool result: cin7_get_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

async def cin7_create_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Cin7 Core product via POST Product.

    Provide the JSON payload as defined by Cin7 Core API. The payload should follow
    the same structure as returned by cin7_product_template. This tool forwards
    the payload to POST Product and returns the API response including the
    newly created product with its assigned ID.

    Use cin7_product_template() to get a template with all available fields.
    Required fields typically include: SKU, Name, and Category.
    
    Example workflow:
    1. Call cin7_product_template() to get the structure
    2. Fill in required fields (SKU, Name, Category) and any optional fields
    3. Pass the completed payload to cin7_create_product()

    Docs: https://dearinventory.docs.apiary.io/#reference/product/product/post
    """
    logger.debug("Tool call: cin7_create_product(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.save_product(payload)
        logger.debug("Tool result: cin7_create_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

async def cin7_update_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core product via PUT Product.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Product and returns the API response.

    Docs: https://dearinventory.docs.apiary.io/#reference/product
    """
    logger.debug("Tool call: cin7_update_product(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.update_product(payload)
        logger.debug("Tool result: cin7_update_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

# ----------------------------- Supplier Tools -----------------------------

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
        page,
        limit,
        name,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_suppliers(page=page, limit=limit, name=name)
        logger.debug("Tool result: cin7_suppliers -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


async def cin7_get_supplier(
    supplier_id: str | None = None,
    name: str | None = None,
) -> Dict[str, Any]:
    """Get a single supplier by ID or name.

    Returns the first matching supplier object.
    """
    logger.debug(
        "Tool call: cin7_get_supplier(supplier_id=%s, name=%s)",
        supplier_id,
        name,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.get_supplier(supplier_id=supplier_id, name=name)
        logger.debug("Tool result: cin7_get_supplier -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


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
    logger.debug("Tool call: cin7_create_supplier(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.save_supplier(payload)
        logger.debug("Tool result: cin7_create_supplier -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


async def cin7_update_supplier(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core supplier via PUT Supplier.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Supplier and returns the API response.

    Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/put
    """
    logger.debug("Tool call: cin7_update_supplier(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.update_supplier(payload)
        logger.debug("Tool result: cin7_update_supplier -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


# ----------------------------- Sale Tools -----------------------------

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
        page,
        limit,
        search,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_sales(page=page, limit=limit, search=search)

        # Project returned sales to only key summary fields plus any explicitly requested fields
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
            # If projection fails for any reason, return the original result
            pass

        logger.debug("Tool result: cin7_sales -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


# ----------------------------- Purchase Order Tools -----------------------------

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
        page,
        limit,
        search,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_purchase_orders(page=page, limit=limit, search=search)

        # Project returned purchase orders to summary fields plus any explicitly requested fields
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
            # If projection fails for any reason, return the original result
            pass

        logger.debug("Tool result: cin7_purchase_orders -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


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
    try:
        result = await client.get_purchase_order(purchase_order_id=purchase_order_id)
        logger.debug("Tool result: cin7_get_purchase_order -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


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
    - Total (line total: (Price × Quantity) - Discount + Tax)

    Example workflow:
    1. Read cin7://templates/purchase_order to get the complete structure
    2. Get product details with cin7_get_product to retrieve ProductID, SKU, Name
    3. Fill in all required PO-level and line-level fields
    4. Calculate Total for each line
    5. Pass the completed payload to cin7_create_purchase_order()
    6. The PO will be created as DRAFT status for user review

    Docs: https://dearinventory.docs.apiary.io/#reference/purchase/purchase-order/post
    """
    logger.debug("Tool call: cin7_create_purchase_order(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.save_purchase_order(payload)
        logger.debug("Tool result: cin7_create_purchase_order -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


# ----------------------------- Stock Transfer Tools -----------------------------

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
        page,
        limit,
        search,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_stock_transfers(page=page, limit=limit, search=search)

        # Project returned stock transfers to summary fields plus any explicitly requested fields
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
            # If projection fails for any reason, return the original result
            pass

        logger.debug("Tool result: cin7_stock_transfers -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


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
    try:
        result = await client.get_stock_transfer(stock_transfer_id=stock_transfer_id)
        logger.debug("Tool result: cin7_get_stock_transfer -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


# ----------------------------- Product Template Resources -----------------------------

async def resource_product_template() -> str:
    """Blank product template with all available fields and required field indicators.

    Use this template to see what fields are available when creating products.
    """
    template = {
        "SKU": "",  # REQUIRED: Unique product identifier
        "Name": "",  # REQUIRED: Product title
        "Category": "",  # REQUIRED: Product category
        "Brand": "",
        "Barcode": "",  # Typically 12-digit UPC
        "Status": "Active",  # REQUIRED: Active or Inactive
        "Type": "Stock",  # REQUIRED: Stock, Service, or Bundle
        "UOM": "Item",  # REQUIRED: Unit of measure (Item, Case, Box, etc.)
        "CostingMethod": "FIFO",  # REQUIRED: FIFO, LIFO, or Average
        "DefaultLocation": "",  # REQUIRED: Default warehouse location
        "PriceTier1": 0.0,
        "PriceTier2": 0.0,
        "PurchasePrice": 0.0,
        "COGSAccount": "5000",
        "RevenueAccount": "4000",
        "InventoryAccount": "1401",
        "PurchaseTaxRule": "Tax Exempt",
        "SaleTaxRule": "Tax Exempt",
        "Suppliers": []  # Array of supplier objects
    }
    return json.dumps(template, indent=2)


async def resource_product_by_id(product_id: str) -> str:
    """Get existing product as template for updates.

    Returns the current product data which can be modified and used with cin7_update_product.
    """
    logger.debug("Resource call: resource_product_by_id(product_id=%s)", product_id)
    client = Cin7Client.from_env()
    try:
        product = await client.get_product(product_id=int(product_id))
        logger.debug("Resource result: resource_product_by_id -> %s", _truncate(str(product)))
        return json.dumps(product, indent=2)
    finally:
        await client.aclose()


async def resource_product_by_sku(sku: str) -> str:
    """Get existing product by SKU as template for updates.

    Returns the current product data which can be modified and used with cin7_update_product.
    """
    logger.debug("Resource call: resource_product_by_sku(sku=%s)", sku)
    client = Cin7Client.from_env()
    try:
        product = await client.get_product(sku=sku)
        logger.debug("Resource result: resource_product_by_sku -> %s", _truncate(str(product)))
        return json.dumps(product, indent=2)
    finally:
        await client.aclose()


# ----------------------------- Supplier Template Resources -----------------------------

async def resource_supplier_template() -> str:
    """Blank supplier template with all available fields.

    Use this template to see what fields are available when creating suppliers.
    """
    template = {
        "Name": "",  # REQUIRED: Supplier name
        "ContactPerson": "",
        "Phone": "",
        "Email": "",
        "Website": "",
        "Address": {
            "Line1": "",
            "Line2": "",
            "City": "",
            "State": "",
            "Postcode": "",
            "Country": ""
        },
        "PaymentTerm": "",
        "Discount": 0.0,
        "TaxRule": "Tax Exempt",
        "Currency": "USD"
    }
    return json.dumps(template, indent=2)


async def resource_supplier_by_id(supplier_id: str) -> str:
    """Get existing supplier as template for updates."""
    logger.debug("Resource call: resource_supplier_by_id(supplier_id=%s)", supplier_id)
    client = Cin7Client.from_env()
    try:
        supplier = await client.get_supplier(supplier_id=supplier_id)
        logger.debug("Resource result: resource_supplier_by_id -> %s", _truncate(str(supplier)))
        return json.dumps(supplier, indent=2)
    finally:
        await client.aclose()


async def resource_supplier_by_name(name: str) -> str:
    """Get existing supplier by name as template for updates."""
    logger.debug("Resource call: resource_supplier_by_name(name=%s)", name)
    client = Cin7Client.from_env()
    try:
        supplier = await client.get_supplier(name=name)
        logger.debug("Resource result: resource_supplier_by_name -> %s", _truncate(str(supplier)))
        return json.dumps(supplier, indent=2)
    finally:
        await client.aclose()


# ----------------------------- Purchase Order Template Resources -----------------------------

async def resource_purchase_order_template() -> str:
    """Blank purchase order template with all available fields.

    Use this template to see what fields are available when creating purchase orders.
    All purchase orders are created with Status="DRAFT" for user review.
    """
    template = {
        "TaskID": "",  # Internal ID (only for updates, leave empty for new POs)
        "Supplier": "",  # REQUIRED: Supplier name or ID
        "Location": "",  # REQUIRED: Warehouse location
        "Status": "DRAFT",  # REQUIRED: Always DRAFT for new POs (user reviews before authorizing)
        "OrderDate": "",  # REQUIRED: Order date (YYYY-MM-DD format)
        "RequiredBy": "",  # Expected delivery date (YYYY-MM-DD format)
        "CurrencyCode": "USD",  # Currency (USD, EUR, etc.)
        "Lines": [  # REQUIRED: Array of order lines
            {
                "ProductID": "",  # REQUIRED*: Product ID (GUID from cin7_get_product)
                "SKU": "",  # REQUIRED*: Product SKU (max 50 chars)
                "Name": "",  # REQUIRED: Product name (max 1024 chars)
                "Quantity": 1.0,  # REQUIRED: Order quantity (decimal, min 1)
                "Price": 0.0,  # REQUIRED: Unit price (decimal, up to 4 decimal places)
                "Tax": 0.0,  # REQUIRED: Tax amount (decimal, up to 4 decimal places)
                "TaxRule": "Tax Exempt",  # REQUIRED: Line tax rule name (max 50 chars)
                "Total": 0.0,  # REQUIRED: Line total for validation (decimal, up to 4 decimal places)
                "Discount": 0.0,  # Optional: Discount 0-100 (decimal, up to 2 decimal places)
                "SupplierSKU": "",  # Optional: Supplier SKU reference (max 50 chars)
                "Comment": "",  # Optional: Comment for this line (max 256 chars)
            }
        ],
        "AdditionalCharges": [  # Optional: Array of additional charges
            {
                "Description": "",  # REQUIRED: Service product name (max 256 chars)
                "Quantity": 1.0,  # REQUIRED: Quantity (decimal, min 1)
                "Price": 0.0,  # REQUIRED: Unit price (decimal, up to 4 decimal places)
                "Tax": 0.0,  # REQUIRED: Tax amount (decimal, up to 4 decimal places)
                "TaxRule": "Tax Exempt",  # REQUIRED: Tax rule name (max 50 chars)
                "Total": 0.0,  # REQUIRED: Line total for validation (decimal, up to 4 decimal places)
                "Reference": "",  # Optional: Comment for this line (max 256 chars)
                "Discount": 0.0,  # Optional: Discount 0-100 (decimal, up to 2 decimal places)
            }
        ],
        "Note": "",  # Optional internal note
        "Memo": "",  # Optional external memo
    }
    return json.dumps(template, indent=2)


async def resource_purchase_order_by_id(purchase_order_id: str) -> str:
    """Get existing purchase order as template for review or updates.

    Returns the current purchase order data.
    """
    logger.debug("Resource call: resource_purchase_order_by_id(purchase_order_id=%s)", purchase_order_id)
    client = Cin7Client.from_env()
    try:
        purchase_order = await client.get_purchase_order(purchase_order_id=purchase_order_id)
        logger.debug("Resource result: resource_purchase_order_by_id -> %s", _truncate(str(purchase_order)))
        return json.dumps(purchase_order, indent=2)
    finally:
        await client.aclose()


# ----------------------------- Workflow Prompts -----------------------------

async def create_product() -> str:
    """Guide for creating a Cin7 Core product with all required fields."""
    return """Create a product in Cin7 Core:

1. Read cin7://templates/product to see all available fields

2. REQUIRED fields for Cin7 API:
   - SKU (unique identifier)
   - Name (product title)
   - Category (product category)
   - Status (Active or Inactive)
   - Type (Stock, Service, or Bundle)
   - UOM (Item, Case, Box, etc.)
   - CostingMethod (FIFO, LIFO, or Average)
   - DefaultLocation (warehouse location)

3. Recommended fields:
   - Brand (manufacturer name)
   - Barcode (typically 12-digit UPC)
   - PriceTier1, PriceTier2 (pricing)
   - PurchasePrice (cost)
   - Suppliers array (supplier information)

4. Accounting fields (often required):
   - COGSAccount, RevenueAccount, InventoryAccount
   - PurchaseTaxRule, SaleTaxRule

5. Use cin7_create_product tool with complete payload

6. Verify creation with cin7_get_product using returned ID
"""


async def update_batch() -> str:
    """Guide for batch updating products with error collection."""
    return """Batch update products in Cin7 Core:

1. Retrieve products to update using cin7_products or snapshot tools

2. For each product, read template: cin7://templates/product/{id}

3. Prepare ALL changes (show user complete before/after list)

4. Get explicit ONE-TIME approval from user for entire batch

5. Execute updates with cin7_update_product for each product:
   - Continue on failures (don't stop)
   - Track successes and failures separately
   - Show progress: ✓ Product 1/N, ✗ Product 2/N (error), etc.

6. Report summary: X succeeded, Y failed

7. For failures, show error details and offer to retry

Error handling: Collect all errors, continue processing, report at end.
"""


async def verify_required_fields() -> str:
    """Check product data completeness before creation/update."""
    return """Verify product has required Cin7 Core fields:

Required fields checklist:
□ SKU
□ Name
□ Category
□ Status
□ Type
□ UOM
□ CostingMethod
□ DefaultLocation

Recommended fields:
□ Brand
□ Barcode
□ Pricing (PriceTier1, PriceTier2, PurchasePrice)

Report any missing or empty required fields before proceeding.
"""


async def create_purchase_order() -> str:
    """Guide for creating a Cin7 Core purchase order."""
    return """Create a purchase order in Cin7 Core:

1. Read cin7://templates/purchase_order to see all available fields

2. REQUIRED fields for Cin7 API:
   - Supplier (supplier name or ID)
   - Location (warehouse location)
   - OrderDate (YYYY-MM-DD format)
   - Lines (array with at least one line item)

3. Each line item REQUIRES:
   - ProductID (GUID from cin7_get_product)
   - SKU (product SKU)
   - Name (product name)
   - Quantity (order quantity, minimum 1)
   - Price (unit price per unit)
   - Tax (tax amount)
   - TaxRule (tax rule name, e.g., "Tax Exempt")
   - Total (line total for validation: (Price × Quantity) - Discount + Tax)

   Optional line fields:
   - Discount (0-100, default 0)
   - SupplierSKU (supplier's SKU)
   - Comment (line comment)

4. Optional: AdditionalCharges array for service charges
   Each additional charge REQUIRES:
   - Description (service product name)
   - Quantity (minimum 1)
   - Price (unit price)
   - Tax (tax amount)
   - TaxRule (tax rule name)
   - Total (line total for validation)

5. IMPORTANT: Status field behavior
   - All new purchase orders are created with Status="DRAFT"
   - This allows user review in Cin7 Core before authorization
   - Users can authorize the PO in the Cin7 Core web interface

6. Optional but recommended PO-level fields:
   - RequiredBy (expected delivery date)
   - CurrencyCode (defaults to USD)
   - Note (internal note)
   - Memo (external memo to supplier)

7. Use cin7_create_purchase_order tool with complete payload

8. Verify creation with cin7_get_purchase_order using returned TaskID

Example workflow:
- Get supplier info with cin7_get_supplier
- Get product info with cin7_get_product (to get ProductID, SKU, Name)
- Calculate line totals: (Price × Quantity) - Discount + Tax
- Build Lines array with all required fields
- Set OrderDate to today's date
- Submit with cin7_create_purchase_order
- PO will be created as DRAFT for user review
"""


# Create default server instance for backward compatibility
server = create_mcp_server()


