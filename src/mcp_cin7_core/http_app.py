from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from .cin7_client import Cin7Client, Cin7ClientError
from .server import (
    cin7_products_snapshot_start,
    cin7_products_snapshot_chunk,
    cin7_products_snapshot_status,
    cin7_products_snapshot_close,
)


# Configure logging for the HTTP app
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

logger = logging.getLogger("mcp_cin7_core.http_app")


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------
BEARER_TOKEN = os.getenv("BEARER_TOKEN")


async def require_bearer_auth(request: Request) -> None:
    """FastAPI dependency that enforces a static bearer token.

    The expected token is provided via the BEARER_TOKEN environment variable.
    If the header is missing or the token does not match, a 401/403 HTTP error
    is raised.
    """

    if not BEARER_TOKEN:
        # Mis-configuration – better to fail closed than leave endpoints open.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bearer token not configured",
        )

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = auth_header[7:].strip()
    if token != BEARER_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    # Auth succeeded – nothing to return.
    return None


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="mcp-cin7-core", version="0.1.0")


@app.get("/health")
async def health(_: None = Depends(require_bearer_auth)) -> Dict[str, Any]:
    return {"ok": True}


@app.get("/me")
async def get_me(_: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.get_me()
    finally:
        await client.aclose()


@app.get("/products")
async def list_products(
    page: int = 1,
    limit: int = 100,
    name: Optional[str] = None,
    sku: Optional[str] = None,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.list_products(page=page, limit=limit, name=name, sku=sku)
    finally:
        await client.aclose()


@app.get("/product")
async def get_product(
    product_id: Optional[int] = None,
    sku: Optional[str] = None,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.get_product(product_id=product_id, sku=sku)
    finally:
        await client.aclose()


@app.get("/product/template")
async def product_template(
    product_id: Optional[int] = None,
    sku: Optional[str] = None,
    include_defaults: bool = True,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    """Return a Product payload template for REST clients.

    - If `product_id` or `sku` is provided, fetch that product and return it as
      an editable template suitable for PUT updates.
    - Otherwise, return a broad template with common fields and placeholders
      suitable for creating new products via POST /product.
    """
    logger.info("HTTP GET /product/template called with product_id=%s, sku=%s, include_defaults=%s", 
                product_id, sku, include_defaults)
    
    if product_id is not None or sku is not None:
        client = Cin7Client.from_env()
        try:
            result = await client.get_product(product_id=product_id, sku=sku)
            logger.info("GET /product/template returning existing product: ID type=%s, keys=%s", 
                       type(result.get("ID")) if isinstance(result, dict) else "N/A",
                       list(result.keys()) if isinstance(result, dict) else "NOT A DICT")
            return result
        except Exception as e:
            logger.error("GET /product/template failed to fetch product: %s", str(e), exc_info=True)
            raise
        finally:
            await client.aclose()

    template: Dict[str, Any] = {
        # Identity
        "ID": 0,
        "SKU": "",
        "Name": "",
        # Classification
        "Category": "",
        "Brand": "",
        "Type": "Stock",
        "CostingMethod": "FIFO",
        # Stock & dimensions
        "Length": 0.0,
        "Width": 0.0,
        "Height": 0.0,
        "Weight": 0.0,
        "UOM": "Item",
        # Visibility & status
        "Status": "Active",
        # Descriptions
        "Description": "",
        "ShortDescription": "",
        # Codes
        "Barcode": "",
        "HSCode": "",
        "CountryOfOrigin": "",
        # Reordering
        "MinimumBeforeReorder": None,
        "ReorderQuantity": None,
        # Pricing examples (expand tiers as needed)
        "PriceTier1": None,
        "PurchasePrice": None,
        # Tax
        "TaxRules": {
            "PurchaseTaxRule": "",
            "SaleTaxRule": "",
        },
        # Misc
        "InternalNote": "",
        "ProductTags": [],
        "AdditionalAttributes": {},
        # Media (example structure if supported)
        "Images": [],
    }

    if not include_defaults:
        # Remove defaulted numeric/enum fields if caller prefers sparse output
        for key in [
            "Type",
            "CostingMethod",
            "UOM",
            "Status",
            "Length",
            "Width",
            "Height",
            "Weight",
        ]:
            template.pop(key, None)

    return template


@app.post("/product")
async def create_product(payload: Dict[str, Any], _: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    logger.info("HTTP POST /product received payload: %s", payload)
    logger.info("Payload type: %s, keys: %s", type(payload), list(payload.keys()) if isinstance(payload, dict) else "NOT A DICT")
    
    client = Cin7Client.from_env()
    try:
        result = await client.save_product(payload)
        logger.info("HTTP POST /product successful, returning: %s", str(result)[:500])
        return result
    except Exception as e:
        logger.error("HTTP POST /product failed with error: %s", str(e), exc_info=True)
        raise
    finally:
        await client.aclose()


@app.put("/product")
async def update_product(payload: Dict[str, Any], _: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    logger.info("HTTP PUT /product received payload: %s", payload)
    logger.info("Payload type: %s, keys: %s", type(payload), list(payload.keys()) if isinstance(payload, dict) else "NOT A DICT")
    if isinstance(payload, dict) and "ID" in payload:
        logger.info("Product ID type: %s, value: %s", type(payload["ID"]), payload["ID"])
    
    client = Cin7Client.from_env()
    try:
        result = await client.update_product(payload)
        logger.info("HTTP PUT /product successful, returning: %s", str(result)[:500])
        return result
    except Exception as e:
        logger.error("HTTP PUT /product failed with error: %s", str(e), exc_info=True)
        raise
    finally:
        await client.aclose()


@app.get("/suppliers")
async def list_suppliers(
    page: int = 1,
    limit: int = 100,
    name: Optional[str] = None,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.list_suppliers(page=page, limit=limit, name=name)
    finally:
        await client.aclose()


@app.get("/supplier")
async def get_supplier(
    supplier_id: Optional[str] = None,
    name: Optional[str] = None,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.get_supplier(supplier_id=supplier_id, name=name)
    finally:
        await client.aclose()


@app.get("/supplier/template")
async def supplier_template(
    supplier_id: Optional[str] = None,
    name: Optional[str] = None,
    include_defaults: bool = True,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    """Return a Supplier payload template for REST clients.

    - If `supplier_id` or `name` is provided, fetch that supplier and return it
      as an editable template suitable for PUT updates.
    - Otherwise, return a broad template with common fields and placeholders
      suitable for creating new suppliers via POST /supplier.
    """
    if supplier_id is not None or name is not None:
        client = Cin7Client.from_env()
        try:
            return await client.get_supplier(supplier_id=supplier_id, name=name)
        finally:
            await client.aclose()

    template: Dict[str, Any] = {
        # Identity
        "ID": "",
        "Name": "",
        # Contact info
        "Contact": "",
        "Phone": "",
        "Fax": "",
        "MobilePhone": "",
        "Email": "",
        "Website": "",
        # Address
        "SupplierAddress": [
            {
                "Line1": "",
                "Line2": "",
                "City": "",
                "State": "",
                "Postcode": "",
                "Country": "",
            }
        ],
        # Banking
        "BankName": "",
        "BankBranch": "",
        "BankAccount": "",
        "BankCode": "",
        # Tax & payment
        "TaxNumber": "",
        "PaymentTerm": "",
        "SupplierDefaultTaxRule": "",
        # Other
        "Comment": "",
        "Currency": "",
    }

    if not include_defaults:
        # Remove empty/defaulted fields if caller prefers sparse output
        template = {k: v for k, v in template.items() if v not in ("", [], {})}

    return template

@app.post("/supplier")
async def create_supplier(payload: Dict[str, Any], _: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.save_supplier(payload)
    finally:
        await client.aclose()


@app.put("/supplier")
async def update_supplier(payload: Dict[str, Any], _: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.update_supplier(payload)
    finally:
        await client.aclose()


@app.get("/sales")
async def list_sales(
    page: int = 1,
    limit: int = 100,
    search: Optional[str] = None,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.list_sales(page=page, limit=limit, search=search)
    finally:
        await client.aclose()


@app.post("/products/snapshot/start")
async def products_snapshot_start(
    payload: Dict[str, Any],
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    """Start a background snapshot build of products.

    Body: { page?, limit?, name?, sku?, fields?[] }
    """
    page = int(payload.get("page", 1))
    limit = int(payload.get("limit", 100))
    name = payload.get("name")
    sku = payload.get("sku")
    fields = payload.get("fields")
    return await cin7_products_snapshot_start(page=page, limit=limit, name=name, sku=sku, fields=fields)


@app.get("/products/snapshot/chunk")
async def products_snapshot_chunk(
    snapshot_id: str,
    offset: int = 0,
    limit: int = 100,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    """Fetch a slice of items from a built or building snapshot."""
    return await cin7_products_snapshot_chunk(snapshot_id=snapshot_id, offset=offset, limit=limit)


@app.get("/products/snapshot/status")
async def products_snapshot_status(
    snapshot_id: str,
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    """Get status and metadata for a running or completed snapshot."""
    return await cin7_products_snapshot_status(snapshot_id)


@app.post("/products/snapshot/close")
async def products_snapshot_close(
    payload: Dict[str, Any],
    _: Dict[str, Any] = Depends(require_bearer_auth),
) -> Dict[str, Any]:
    """Close and clean up a snapshot, cancelling work if still running.

    Body: { snapshot_id }
    """
    snapshot_id = str(payload.get("snapshot_id"))
    return await cin7_products_snapshot_close(snapshot_id)


@app.exception_handler(Cin7ClientError)
async def handle_client_error(_: Request, exc: Cin7ClientError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": str(exc)},
    )


