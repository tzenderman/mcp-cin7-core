from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from .cin7_client import Cin7Client, Cin7ClientError


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


@app.post("/product")
async def create_product(payload: Dict[str, Any], _: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.save_product(payload)
    finally:
        await client.aclose()


@app.put("/product")
async def update_product(payload: Dict[str, Any], _: Dict[str, Any] = Depends(require_bearer_auth)) -> Dict[str, Any]:
    client = Cin7Client.from_env()
    try:
        return await client.update_product(payload)
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


@app.exception_handler(Cin7ClientError)
async def handle_client_error(_: Request, exc: Cin7ClientError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": str(exc)},
    )


