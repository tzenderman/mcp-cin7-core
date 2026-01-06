# Stock Availability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add MCP tools to expose Cin7 ProductAvailability endpoint for stock levels per location.

**Architecture:** Add client methods for ProductAvailability API, then MCP tools following existing patterns. Includes snapshot system for large catalogs using the same pattern as product snapshots.

**Tech Stack:** Python, httpx, FastMCP, pytest

---

## Task 1: Add Client Methods

**Files:**
- Modify: `src/mcp_cin7_core/cin7_client.py` (after line 716, before `get_stock_transfer`)

**Step 1: Write the failing test**

Create `tests/test_cin7_client.py`:

```python
"""Tests for Cin7 client methods."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from mcp_cin7_core.cin7_client import Cin7Client, Cin7ClientError


@pytest.fixture
def mock_client():
    """Create a Cin7Client with mocked httpx client."""
    with patch.dict("os.environ", {
        "CIN7_ACCOUNT_ID": "test_account",
        "CIN7_API_KEY": "test_key",
    }):
        client = Cin7Client.from_env()
        client.client = MagicMock()
        return client


class TestListProductAvailability:
    """Tests for list_product_availability method."""

    @pytest.mark.asyncio
    async def test_returns_availability_list(self, mock_client):
        """Should return ProductAvailabilityList from API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ProductAvailabilityList": [
                {"SKU": "TEST-001", "Location": "Main", "OnHand": 50, "Available": 45}
            ],
            "Total": 1
        }
        mock_client.client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.list_product_availability(page=1, limit=100)

        assert "ProductAvailabilityList" in result
        assert len(result["ProductAvailabilityList"]) == 1
        assert result["ProductAvailabilityList"][0]["SKU"] == "TEST-001"
        mock_client.client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_filter_params(self, mock_client):
        """Should pass SKU and location filters to API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ProductAvailabilityList": [], "Total": 0}
        mock_client.client.get = AsyncMock(return_value=mock_response)

        await mock_client.list_product_availability(
            page=2, limit=50, sku="TEST-001", location="Main"
        )

        call_args = mock_client.client.get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Page"] == 2
        assert params["Limit"] == 50
        assert params["SKU"] == "TEST-001"
        assert params["Location"] == "Main"


class TestGetProductAvailability:
    """Tests for get_product_availability method."""

    @pytest.mark.asyncio
    async def test_returns_all_locations_for_sku(self, mock_client):
        """Should return all location entries for a single SKU."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ProductAvailabilityList": [
                {"SKU": "TEST-001", "Location": "Main", "OnHand": 50},
                {"SKU": "TEST-001", "Location": "Store", "OnHand": 10},
            ],
            "Total": 2
        }
        mock_client.client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_product_availability(sku="TEST-001")

        assert len(result) == 2
        assert result[0]["Location"] == "Main"
        assert result[1]["Location"] == "Store"

    @pytest.mark.asyncio
    async def test_raises_without_sku_or_product_id(self, mock_client):
        """Should raise error if neither SKU nor product_id provided."""
        with pytest.raises(Cin7ClientError, match="requires product_id or sku"):
            await mock_client.get_product_availability()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cin7_client.py -v`
Expected: FAIL with "AttributeError: 'Cin7Client' object has no attribute 'list_product_availability'"

**Step 3: Write minimal implementation**

Add to `src/mcp_cin7_core/cin7_client.py` (after `update_product_suppliers`, before `get_stock_transfer`):

```python
    async def list_product_availability(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List product availability with stock levels per location.

        Maps to GET ref/productavailability endpoint.
        Returns: ProductID, SKU, Location, OnHand, Available,
                 Allocated, OnOrder, InTransit, NextDeliveryDate, Bin, Batch

        Docs: https://dearinventory.docs.apiary.io/#reference/product/product-availability
        """
        params: Dict[str, Any] = {"Page": page, "Limit": limit}
        if product_id:
            params["ProductID"] = product_id
        if sku:
            params["SKU"] = sku
        if location:
            params["Location"] = location

        response = await self.client.get("ref/productavailability", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"raw": _truncate(response.text or "")}

        if response.status_code == 200:
            return data if isinstance(data, dict) else {"result": data}

        raise Cin7ClientError(
            f"ProductAvailability list error: {response.status_code} {response.text[:200]}"
        )

    async def get_product_availability(
        self,
        *,
        product_id: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get availability for a single product across all locations.

        Returns list of location entries (one product can have multiple
        location records).
        """
        if not product_id and not sku:
            raise Cin7ClientError("get_product_availability requires product_id or sku")

        result = await self.list_product_availability(
            product_id=product_id,
            sku=sku,
            limit=1000,
        )
        return result.get("ProductAvailabilityList", [])
```

**Step 4: Add List import at top of file**

Update the typing import at line 7:

```python
from typing import Any, Dict, Callable, Optional, List
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cin7_client.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/mcp_cin7_core/cin7_client.py tests/test_cin7_client.py
git commit -m "feat(client): add list_product_availability and get_product_availability methods"
```

---

## Task 2: Add Basic MCP Tools

**Files:**
- Modify: `src/mcp_cin7_core/mcp_server.py`

**Step 1: Write the failing test**

Add to `tests/test_mcp_server.py`:

```python
"""Tests for MCP server tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestStockLevelsTools:
    """Tests for stock availability tools."""

    @pytest.mark.asyncio
    async def test_cin7_stock_levels_returns_projected_data(self):
        """Should return stock levels with default field projection."""
        mock_result = {
            "ProductAvailabilityList": [
                {
                    "SKU": "TEST-001",
                    "Location": "Main",
                    "OnHand": 50.0,
                    "Available": 45.0,
                    "Allocated": 5.0,
                    "OnOrder": 10.0,
                    "InTransit": 0.0,
                    "Bin": "A1",
                    "Batch": "LOT001",
                    "ProductID": "abc-123",
                },
            ],
            "Total": 1,
        }

        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value=mock_result)
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import cin7_stock_levels

            result = await cin7_stock_levels(page=1, limit=100)

            # Default projection: SKU, Location, OnHand, Available
            item = result["ProductAvailabilityList"][0]
            assert "SKU" in item
            assert "Location" in item
            assert "OnHand" in item
            assert "Available" in item
            # These should be excluded by default
            assert "Bin" not in item
            assert "Batch" not in item
            assert "ProductID" not in item

    @pytest.mark.asyncio
    async def test_cin7_stock_levels_includes_extra_fields(self):
        """Should include additional fields when requested."""
        mock_result = {
            "ProductAvailabilityList": [
                {
                    "SKU": "TEST-001",
                    "Location": "Main",
                    "OnHand": 50.0,
                    "Available": 45.0,
                    "Allocated": 5.0,
                    "Bin": "A1",
                },
            ],
            "Total": 1,
        }

        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value=mock_result)
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import cin7_stock_levels

            result = await cin7_stock_levels(fields=["Allocated", "Bin"])

            item = result["ProductAvailabilityList"][0]
            assert "Allocated" in item
            assert "Bin" in item

    @pytest.mark.asyncio
    async def test_cin7_get_stock_returns_all_locations(self):
        """Should return all locations for a single product."""
        mock_result = [
            {"SKU": "TEST-001", "Location": "Main", "OnHand": 50.0, "Available": 45.0},
            {"SKU": "TEST-001", "Location": "Store", "OnHand": 10.0, "Available": 10.0},
        ]

        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.get_product_availability = AsyncMock(return_value=mock_result)
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import cin7_get_stock

            result = await cin7_get_stock(sku="TEST-001")

            assert result["sku"] == "TEST-001"
            assert len(result["locations"]) == 2
            assert result["total_on_hand"] == 60.0
            assert result["total_available"] == 55.0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_server.py::TestStockLevelsTools -v`
Expected: FAIL with "cannot import name 'cin7_stock_levels'"

**Step 3: Write the implementation**

Add to `src/mcp_cin7_core/mcp_server.py` (after stock transfer tools, before resource definitions):

```python
# ----------------------------- Stock Availability Tools -----------------------------

def _project_stock_items(items: List[Dict[str, Any]], fields: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Project stock availability items to requested fields."""
    base_fields = {"SKU", "Location", "OnHand", "Available"}
    requested_fields = set(fields or [])
    allowed = base_fields | requested_fields
    projected: List[Dict[str, Any]] = []
    for it in items:
        if isinstance(it, dict):
            projected.append({k: v for k, v in it.items() if k in allowed})
        else:
            projected.append(it)
    return projected


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
    try:
        result = await client.list_product_availability(
            page=page, limit=limit, location=location
        )

        # Apply field projection
        if isinstance(result, dict):
            items = result.get("ProductAvailabilityList")
            if isinstance(items, list):
                result["ProductAvailabilityList"] = _project_stock_items(items, fields)

        logger.debug("Tool result: cin7_stock_levels -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


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
    try:
        locations = await client.get_product_availability(
            sku=sku, product_id=product_id
        )

        # Aggregate totals
        total_on_hand = sum(loc.get("OnHand", 0) or 0 for loc in locations)
        total_available = sum(loc.get("Available", 0) or 0 for loc in locations)

        # Determine SKU from results if not provided
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

        logger.debug("Tool result: cin7_get_stock -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()
```

**Step 4: Register tools in create_mcp_server**

Add these lines in the `create_mcp_server` function after stock transfer registrations (around line 87):

```python
    server.tool()(cin7_stock_levels)
    server.tool()(cin7_get_stock)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_server.py::TestStockLevelsTools -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/mcp_cin7_core/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(tools): add cin7_stock_levels and cin7_get_stock MCP tools"
```

---

## Task 3: Add Stock Snapshot System

**Files:**
- Modify: `src/mcp_cin7_core/mcp_server.py`

**Step 1: Write the failing test**

Add to `tests/test_mcp_server.py`:

```python
class TestStockSnapshotTools:
    """Tests for stock snapshot tools."""

    @pytest.mark.asyncio
    async def test_snapshot_start_returns_id(self):
        """Should return a snapshot ID when started."""
        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [],
                "Total": 0,
            })
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import cin7_stock_snapshot_start

            result = await cin7_stock_snapshot_start()

            assert "snapshotId" in result
            assert isinstance(result["snapshotId"], str)
            assert len(result["snapshotId"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_snapshot_status_returns_progress(self):
        """Should return snapshot status."""
        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [{"SKU": "A", "Location": "M", "OnHand": 1, "Available": 1}],
                "Total": 1,
            })
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import (
                cin7_stock_snapshot_start,
                cin7_stock_snapshot_status,
            )
            import asyncio

            start_result = await cin7_stock_snapshot_start()
            snapshot_id = start_result["snapshotId"]

            # Give snapshot task time to complete
            await asyncio.sleep(0.1)

            status = await cin7_stock_snapshot_status(snapshot_id)

            assert status["snapshotId"] == snapshot_id
            assert "ready" in status
            assert "total" in status

    @pytest.mark.asyncio
    async def test_snapshot_chunk_returns_items(self):
        """Should return items from snapshot."""
        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [
                    {"SKU": "A", "Location": "M", "OnHand": 1, "Available": 1},
                    {"SKU": "B", "Location": "M", "OnHand": 2, "Available": 2},
                ],
                "Total": 2,
            })
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import (
                cin7_stock_snapshot_start,
                cin7_stock_snapshot_chunk,
            )
            import asyncio

            start_result = await cin7_stock_snapshot_start()
            snapshot_id = start_result["snapshotId"]

            # Wait for build
            await asyncio.sleep(0.1)

            chunk = await cin7_stock_snapshot_chunk(snapshot_id, offset=0, limit=10)

            assert "items" in chunk
            assert len(chunk["items"]) == 2
            assert chunk["nextOffset"] is None  # No more items

    @pytest.mark.asyncio
    async def test_snapshot_close_cleans_up(self):
        """Should clean up snapshot on close."""
        with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [],
                "Total": 0,
            })
            mock_client.aclose = AsyncMock()
            mock_class.from_env.return_value = mock_client

            from mcp_cin7_core.mcp_server import (
                cin7_stock_snapshot_start,
                cin7_stock_snapshot_close,
                cin7_stock_snapshot_status,
            )

            start_result = await cin7_stock_snapshot_start()
            snapshot_id = start_result["snapshotId"]

            close_result = await cin7_stock_snapshot_close(snapshot_id)
            assert close_result["ok"] is True

            # Verify snapshot is gone
            status = await cin7_stock_snapshot_status(snapshot_id)
            assert "error" in status
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_server.py::TestStockSnapshotTools -v`
Expected: FAIL with "cannot import name 'cin7_stock_snapshot_start'"

**Step 3: Write the implementation**

Add to `src/mcp_cin7_core/mcp_server.py` (after basic stock tools):

```python
# ----------------------------- Stock Snapshot Storage -----------------------------

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


_stock_snapshots: Dict[str, StockSnapshot] = {}
_stock_snapshot_tasks: Dict[str, asyncio.Task] = {}


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
        per_page = min(limit, 1000)  # Cin7 max is 1000
        while True:
            result = await client.list_product_availability(
                page=current_page, limit=per_page, location=location
            )
            items = []
            if isinstance(result, dict):
                plist = result.get("ProductAvailabilityList")
                if isinstance(plist, list):
                    items = plist

            # Apply field projection
            projected = _project_stock_items(items, fields)

            if snap is None:
                break
            if len(snap.items) + len(projected) > SNAPSHOT_MAX_ITEMS:
                snap.error = f"Snapshot item cap reached ({SNAPSHOT_MAX_ITEMS})."
                break

            snap.items.extend(projected)
            snap.total = len(snap.items)

            # Stop if no more pages
            if len(items) < per_page:
                break
            current_page += 1

        if snap is not None and not snap.error:
            snap.ready = True
    except Exception as exc:
        if snap is not None:
            snap.error = str(exc)
    finally:
        await client.aclose()


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

    return {
        "snapshotId": sid,
        "ready": snap.ready,
        "total": snap.total,
    }


async def cin7_stock_snapshot_status(snapshot_id: str) -> Dict[str, Any]:
    """Get status and metadata for a running or completed stock snapshot."""
    _cleanup_expired_stock_snapshots()
    snap = _stock_snapshots.get(snapshot_id)
    if not snap:
        return {"error": "snapshot not found"}
    return {
        "snapshotId": snap.id,
        "ready": snap.ready,
        "total": snap.total,
        "error": snap.error,
        "params": snap.params,
    }


async def cin7_stock_snapshot_chunk(
    snapshot_id: str,
    offset: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch a slice of items from a built or building stock snapshot.

    If the snapshot is still building, this returns whatever is available.
    """
    _cleanup_expired_stock_snapshots()
    snap = _stock_snapshots.get(snapshot_id)
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


async def cin7_stock_snapshot_close(snapshot_id: str) -> Dict[str, Any]:
    """Close and clean up a stock snapshot, cancelling work if still running."""
    snap = _stock_snapshots.pop(snapshot_id, None)
    task = _stock_snapshot_tasks.pop(snapshot_id, None)
    if task and not task.done():
        task.cancel()
    return {"ok": True, "snapshotId": snapshot_id, "existed": snap is not None}
```

**Step 4: Register snapshot tools in create_mcp_server**

Add these lines after the basic stock tools:

```python
    server.tool()(cin7_stock_snapshot_start)
    server.tool()(cin7_stock_snapshot_status)
    server.tool()(cin7_stock_snapshot_chunk)
    server.tool()(cin7_stock_snapshot_close)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_server.py::TestStockSnapshotTools -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/mcp_cin7_core/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(tools): add stock availability snapshot system"
```

---

## Task 4: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add stock availability section**

Add after the "Stock Transfers" section in the MCP Protocol Reference:

```markdown
**Stock Availability:**
- `cin7_stock_levels(page, limit, location, fields)` - List stock levels across all products/locations
- `cin7_get_stock(sku, product_id)` - Get stock levels for a single product

**Stock Availability Snapshots:**
- `cin7_stock_snapshot_start(page, limit, location, fields)` - Start background build
- `cin7_stock_snapshot_status(snapshot_id)` - Check build progress
- `cin7_stock_snapshot_chunk(snapshot_id, offset, limit)` - Fetch chunk
- `cin7_stock_snapshot_close(snapshot_id)` - Clean up
```

**Step 2: Add common operations section**

Add a new section for working with stock data:

```markdown
### Checking stock levels

Single product lookup:
```python
# Get stock for a single SKU across all locations
result = await cin7_get_stock(sku="PRODUCT-SKU")
# Returns: sku, locations[], total_on_hand, total_available
```

### Syncing stock with external systems

For large catalogs, use the snapshot workflow:

1. Start: `cin7_stock_snapshot_start(fields=["Allocated", "OnOrder"])`
2. Poll status: `cin7_stock_snapshot_status(snapshot_id="...")`
3. Fetch chunks: `cin7_stock_snapshot_chunk(snapshot_id="...", offset=0, limit=500)`
4. Continue fetching with `nextOffset` until `null`
5. Clean up: `cin7_stock_snapshot_close(snapshot_id="...")`
```

**Step 3: Add response fields documentation**

Add to the architecture section:

```markdown
### Stock Availability Response Fields

| Field | Type | Description |
|-------|------|-------------|
| SKU | string | Product identifier |
| Location | string | Warehouse name |
| OnHand | decimal | Physical stock quantity |
| Available | decimal | OnHand - Allocated |
| Allocated | decimal | Reserved for pending orders |
| OnOrder | decimal | On purchase orders, not received |
| InTransit | decimal | Being transferred |
| NextDeliveryDate | datetime | Expected delivery |
| Bin | string | Bin location |
| Batch | string | Batch/lot number |
```

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add stock availability tools documentation"
```

---

## Task 5: Run Full Test Suite and Verify

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Quick import check**

Run: `uv run python -c "from mcp_cin7_core.mcp_server import cin7_stock_levels, cin7_get_stock, cin7_stock_snapshot_start; print('OK')"`
Expected: "OK"

**Step 3: Commit any fixes if needed**

If tests fail, fix issues and commit.

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Client methods | `cin7_client.py`, `test_cin7_client.py` |
| 2 | Basic MCP tools | `mcp_server.py`, `test_mcp_server.py` |
| 3 | Snapshot system | `mcp_server.py`, `test_mcp_server.py` |
| 4 | Documentation | `CLAUDE.md` |
| 5 | Final verification | Run tests |

Total: 5 tasks, ~6 commits
