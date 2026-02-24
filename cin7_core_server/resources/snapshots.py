"""Snapshot tools for products and stock availability."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_items, project_stock_items

logger = logging.getLogger("cin7_core_server.resources.snapshots")

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


@dataclass
class StockSnapshot:
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

_stock_snapshots: Dict[str, StockSnapshot] = {}
_stock_snapshot_tasks: Dict[str, asyncio.Task] = {}


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


def _cleanup_expired_stock_snapshots() -> None:
    expired: List[str] = []
    now = time.time()
    for sid, snap in list(_stock_snapshots.items()):
        if (now - snap.created_at) > SNAPSHOT_TTL_SECONDS:
            expired.append(sid)
    for sid in expired:
        _stock_snapshots.pop(sid, None)
        task = _stock_snapshot_tasks.pop(sid, None)
        if task and not task.done():
            task.cancel()


# ----------------------------- Product Snapshot Build -----------------------------

async def _build_snapshot(sid: str, page: int, limit: int, name: Optional[str], sku: Optional[str], fields: Optional[List[str]]) -> None:
    client = Cin7Client.from_env()
    snap = _snapshots.get(sid)
    try:
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

            projected = project_items(products, fields)

            if snap is None:
                break
            if len(snap.items) + len(projected) > SNAPSHOT_MAX_ITEMS:
                snap.error = f"Snapshot item cap reached ({SNAPSHOT_MAX_ITEMS})."
                break
            snap.items.extend(projected)
            snap.total = len(snap.items)

            if len(products) < per_page:
                break
            current_page += 1

        if snap is not None and not snap.error:
            snap.ready = True
    except Exception as exc:
        if snap is not None:
            snap.error = str(exc)


# ----------------------------- Stock Snapshot Build -----------------------------

async def _build_stock_snapshot(
    sid: str,
    page: int,
    limit: int,
    location: Optional[str],
    fields: Optional[List[str]],
) -> None:
    client = Cin7Client.from_env()
    snap = _stock_snapshots.get(sid)
    try:
        current_page = page
        per_page = min(limit, 1000)
        while True:
            result = await client.list_product_availability(
                page=current_page, limit=per_page, location=location
            )
            items = []
            if isinstance(result, dict):
                plist = result.get("ProductAvailabilityList")
                if isinstance(plist, list):
                    items = plist

            projected = project_stock_items(items, fields)

            if snap is None:
                break
            if len(snap.items) + len(projected) > SNAPSHOT_MAX_ITEMS:
                snap.error = f"Snapshot item cap reached ({SNAPSHOT_MAX_ITEMS})."
                break

            snap.items.extend(projected)
            snap.total = len(snap.items)

            if len(items) < per_page:
                break
            current_page += 1

        if snap is not None and not snap.error:
            snap.ready = True
    except Exception as exc:
        if snap is not None:
            snap.error = str(exc)


# ----------------------------- Product Snapshot Tools -----------------------------

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


# ----------------------------- Stock Snapshot Tools -----------------------------

async def cin7_stock_snapshot_start(
    page: int = 1,
    limit: int = 1000,
    location: str | None = None,
    fields: list[str] | None = None,
) -> Dict[str, Any]:
    """Start a server-side snapshot build of stock availability.

    Returns a snapshotId that can be used to fetch chunks, check status, or close.
    The snapshot applies default projection (SKU, Location, OnHand, Available) plus any requested fields.

    Parameters:
    - page: Starting page (1-based)
    - limit: Items per page during build (max 1000)
    - location: Filter by location name
    - fields: Additional fields beyond defaults
    """
    logger.debug(
        "Tool call: cin7_stock_snapshot_start(page=%s, limit=%s, location=%s, fields=%s)",
        page, limit, location, fields,
    )
    _cleanup_expired_stock_snapshots()

    sid = str(uuid.uuid4())
    snap = StockSnapshot(
        id=sid,
        created_at=time.time(),
        total=0,
        items=[],
        ready=False,
        error=None,
        params={
            "page": page,
            "limit": limit,
            "location": location,
            "fields": list(fields or []),
        },
    )
    _stock_snapshots[sid] = snap

    task = asyncio.create_task(_build_stock_snapshot(sid, page, limit, location, fields))
    _stock_snapshot_tasks[sid] = task

    result = {
        "snapshotId": sid,
        "ready": snap.ready,
        "total": snap.total,
    }
    logger.debug("Tool result: cin7_stock_snapshot_start -> %s", truncate(str(result)))
    return result


async def cin7_stock_snapshot_status(snapshot_id: str) -> Dict[str, Any]:
    """Get status and metadata for a running or completed stock snapshot."""
    logger.debug(
        "Tool call: cin7_stock_snapshot_status(snapshot_id=%s)",
        snapshot_id,
    )
    _cleanup_expired_stock_snapshots()
    snap = _stock_snapshots.get(snapshot_id)
    if not snap:
        result = {"error": "snapshot not found"}
        logger.debug("Tool result: cin7_stock_snapshot_status -> %s", truncate(str(result)))
        return result
    result = {
        "snapshotId": snap.id,
        "ready": snap.ready,
        "total": snap.total,
        "error": snap.error,
        "params": snap.params,
    }
    logger.debug("Tool result: cin7_stock_snapshot_status -> %s", truncate(str(result)))
    return result


async def cin7_stock_snapshot_chunk(
    snapshot_id: str,
    offset: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch a slice of items from a built or building stock snapshot.

    If the snapshot is still building, this returns whatever is available.
    """
    logger.debug(
        "Tool call: cin7_stock_snapshot_chunk(snapshot_id=%s, offset=%s, limit=%s)",
        snapshot_id, offset, limit,
    )
    _cleanup_expired_stock_snapshots()
    snap = _stock_snapshots.get(snapshot_id)
    if not snap:
        result = {"error": "snapshot not found"}
        logger.debug("Tool result: cin7_stock_snapshot_chunk -> %s", truncate(str(result)))
        return result
    start = max(0, int(offset))
    end = max(start, start + int(limit))
    items = snap.items[start:end]
    next_offset = end if end < len(snap.items) else None
    result = {
        "snapshotId": snap.id,
        "ready": snap.ready,
        "total": snap.total,
        "items": items,
        "nextOffset": next_offset,
    }
    logger.debug("Tool result: cin7_stock_snapshot_chunk -> %s", truncate(str(result)))
    return result


async def cin7_stock_snapshot_close(snapshot_id: str) -> Dict[str, Any]:
    """Close and clean up a stock snapshot, cancelling work if still running."""
    logger.debug(
        "Tool call: cin7_stock_snapshot_close(snapshot_id=%s)",
        snapshot_id,
    )
    snap = _stock_snapshots.pop(snapshot_id, None)
    task = _stock_snapshot_tasks.pop(snapshot_id, None)
    if task and not task.done():
        task.cancel()
    result = {"ok": True, "snapshotId": snapshot_id, "existed": snap is not None}
    logger.debug("Tool result: cin7_stock_snapshot_close -> %s", truncate(str(result)))
    return result
