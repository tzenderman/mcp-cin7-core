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
from mcp.server.fastmcp import FastMCP

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

server = FastMCP("mcp-cin7-core")
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



@server.tool()
async def cin7_status() -> Dict[str, Any]:
    """Verify Cin7 Core credentials by fetching a minimal page of products."""
    logger.info("Tool call: cin7_status()")
    client = Cin7Client.from_env()
    try:
        result = await client.health_check()
        logger.info("Tool result: cin7_status() -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
async def cin7_me() -> Dict[str, Any]:
    """Call Cin7 Core Me endpoint to verify identity and account context."""
    logger.info("Tool call: cin7_me()")
    client = Cin7Client.from_env()
    try:
        result = await client.get_me()
        logger.info("Tool result: cin7_me() -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
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

@server.tool()
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

@server.tool()
async def cin7_products_snapshot_close(snapshot_id: str) -> Dict[str, Any]:
    """Close and clean up a snapshot, cancelling work if still running."""
    snap = _snapshots.pop(snapshot_id, None)
    task = _snapshot_tasks.pop(snapshot_id, None)
    if task and not task.done():
        task.cancel()
    return {"ok": True, "snapshotId": snapshot_id, "existed": snap is not None}

@server.tool()
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
    logger.info(
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

        logger.info("Tool result: cin7_products -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
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

@server.tool()
async def cin7_get_product(
    product_id: int | None = None,
    sku: str | None = None,
) -> Dict[str, Any]:
    """Get a single product by ID or SKU.

    Returns the first matching product object.
    """
    logger.info(
        "Tool call: cin7_get_product(product_id=%s, sku=%s)",
        product_id,
        sku,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.get_product(product_id=product_id, sku=sku)
        logger.info("Tool result: cin7_get_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

@server.tool()
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
    logger.info("Tool call: cin7_create_product(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.save_product(payload)
        logger.info("Tool result: cin7_create_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

@server.tool()
async def cin7_update_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core product via PUT Product.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Product and returns the API response.

    Docs: https://dearinventory.docs.apiary.io/#reference/product
    """
    logger.info("Tool call: cin7_update_product(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.update_product(payload)
        logger.info("Tool result: cin7_update_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

# ----------------------------- Supplier Tools -----------------------------

@server.tool()
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
    logger.info(
        "Tool call: cin7_suppliers(page=%s, limit=%s, name=%s)",
        page,
        limit,
        name,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_suppliers(page=page, limit=limit, name=name)
        logger.info("Tool result: cin7_suppliers -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
async def cin7_get_supplier(
    supplier_id: str | None = None,
    name: str | None = None,
) -> Dict[str, Any]:
    """Get a single supplier by ID or name.

    Returns the first matching supplier object.
    """
    logger.info(
        "Tool call: cin7_get_supplier(supplier_id=%s, name=%s)",
        supplier_id,
        name,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.get_supplier(supplier_id=supplier_id, name=name)
        logger.info("Tool result: cin7_get_supplier -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
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
    logger.info("Tool call: cin7_create_supplier(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.save_supplier(payload)
        logger.info("Tool result: cin7_create_supplier -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
async def cin7_update_supplier(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core supplier via PUT Supplier.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Supplier and returns the API response.

    Docs: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/put
    """
    logger.info("Tool call: cin7_update_supplier(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.update_supplier(payload)
        logger.info("Tool result: cin7_update_supplier -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


# ----------------------------- Sale Tools -----------------------------

@server.tool()
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
    logger.info(
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

        logger.info("Tool result: cin7_sales -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


# ----------------------------- Product Template Resources -----------------------------

@server.resource("cin7://templates/product")
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


@server.resource("cin7://templates/product/{product_id}")
async def resource_product_by_id(product_id: str) -> str:
    """Get existing product as template for updates.

    Returns the current product data which can be modified and used with cin7_update_product.
    """
    logger.info("Resource call: resource_product_by_id(product_id=%s)", product_id)
    client = Cin7Client.from_env()
    try:
        product = await client.get_product(product_id=int(product_id))
        logger.info("Resource result: resource_product_by_id -> %s", _truncate(str(product)))
        return json.dumps(product, indent=2)
    finally:
        await client.aclose()


@server.resource("cin7://templates/product/sku/{sku}")
async def resource_product_by_sku(sku: str) -> str:
    """Get existing product by SKU as template for updates.

    Returns the current product data which can be modified and used with cin7_update_product.
    """
    logger.info("Resource call: resource_product_by_sku(sku=%s)", sku)
    client = Cin7Client.from_env()
    try:
        product = await client.get_product(sku=sku)
        logger.info("Resource result: resource_product_by_sku -> %s", _truncate(str(product)))
        return json.dumps(product, indent=2)
    finally:
        await client.aclose()


# ----------------------------- Supplier Template Resources -----------------------------

@server.resource("cin7://templates/supplier")
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


@server.resource("cin7://templates/supplier/{supplier_id}")
async def resource_supplier_by_id(supplier_id: str) -> str:
    """Get existing supplier as template for updates."""
    logger.info("Resource call: resource_supplier_by_id(supplier_id=%s)", supplier_id)
    client = Cin7Client.from_env()
    try:
        supplier = await client.get_supplier(supplier_id=supplier_id)
        logger.info("Resource result: resource_supplier_by_id -> %s", _truncate(str(supplier)))
        return json.dumps(supplier, indent=2)
    finally:
        await client.aclose()


@server.resource("cin7://templates/supplier/name/{name}")
async def resource_supplier_by_name(name: str) -> str:
    """Get existing supplier by name as template for updates."""
    logger.info("Resource call: resource_supplier_by_name(name=%s)", name)
    client = Cin7Client.from_env()
    try:
        supplier = await client.get_supplier(name=name)
        logger.info("Resource result: resource_supplier_by_name -> %s", _truncate(str(supplier)))
        return json.dumps(supplier, indent=2)
    finally:
        await client.aclose()


# ----------------------------- Workflow Prompts -----------------------------

@server.prompt()
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


@server.prompt()
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


@server.prompt()
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


