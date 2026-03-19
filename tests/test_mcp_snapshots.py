"""Comprehensive tests for snapshot lifecycle (product and stock snapshots)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cin7_core_server.resources.snapshots as server_mod
from cin7_core_server.resources.snapshots import (
    cin7_products_snapshot_start,
    cin7_products_snapshot_status,
    cin7_products_snapshot_chunk,
    cin7_products_snapshot_close,
    cin7_stock_snapshot_start,
    cin7_stock_snapshot_status,
    cin7_stock_snapshot_chunk,
    cin7_stock_snapshot_close,
)


@pytest.fixture(autouse=True)
def cleanup_snapshots():
    """Clear all snapshot state after every test."""
    yield
    # Cancel any lingering tasks before clearing
    for task in list(server_mod._snapshot_tasks.values()):
        if not task.done():
            task.cancel()
    for task in list(server_mod._stock_snapshot_tasks.values()):
        if not task.done():
            task.cancel()
    server_mod._snapshots.clear()
    server_mod._snapshot_tasks.clear()
    server_mod._stock_snapshots.clear()
    server_mod._stock_snapshot_tasks.clear()


def _mock_cin7_client(**method_mocks):
    """Helper: create a patched Cin7Client context manager.

    Pass keyword arguments mapping method names to AsyncMock return values,
    e.g. ``_mock_cin7_client(list_products=AsyncMock(return_value={...}))``.
    """
    mock_client = MagicMock()
    for name, mock in method_mocks.items():
        setattr(mock_client, name, mock)
    patcher = patch("cin7_core_server.resources.snapshots.Cin7Client")
    mock_class = patcher.start()
    mock_class.from_env.return_value = mock_client
    return patcher, mock_client


# ---------------------------------------------------------------------------
# Product Snapshot Lifecycle
# ---------------------------------------------------------------------------


class TestProductSnapshotLifecycle:
    """Tests for the product snapshot start / status / chunk / close flow."""

    async def test_start_returns_snapshot_id(self):
        """cin7_products_snapshot_start should return a valid UUID snapshot ID."""
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": [], "Total": 0}),
        )
        try:
            result = await cin7_products_snapshot_start()
            assert "snapshotId" in result
            assert isinstance(result["snapshotId"], str)
            assert len(result["snapshotId"]) == 36  # UUID format: 8-4-4-4-12
            assert result["ready"] is False or result["ready"] is True
            assert "total" in result
        finally:
            patcher.stop()

    async def test_status_returns_progress_after_build(self):
        """After the background task completes, status should show ready=True."""
        products = [
            {"SKU": "A", "Name": "Alpha", "Category": "Cat1"},
            {"SKU": "B", "Name": "Beta", "Category": "Cat2"},
        ]
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": products, "Total": 2}),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]

            # Let background task finish
            await asyncio.sleep(0.1)

            status = await cin7_products_snapshot_status(sid)
            assert status["snapshotId"] == sid
            assert status["ready"] is True
            assert status["total"] == 2
            assert status["error"] is None
            assert "params" in status
        finally:
            patcher.stop()

    async def test_chunk_with_projection(self):
        """Items returned by chunk should only contain SKU, Name + requested fields."""
        products = [
            {"SKU": "A", "Name": "Alpha", "Category": "Cat1", "Brand": "B1", "PriceTier1": 9.99},
            {"SKU": "B", "Name": "Beta", "Category": "Cat2", "Brand": "B2", "PriceTier1": 19.99},
        ]
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": products, "Total": 2}),
        )
        try:
            start = await cin7_products_snapshot_start(fields=["Category"])
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            chunk = await cin7_products_snapshot_chunk(sid, offset=0, limit=10)
            assert len(chunk["items"]) == 2

            for item in chunk["items"]:
                # Base fields always present
                assert "SKU" in item
                assert "Name" in item
                # Requested field included
                assert "Category" in item
                # Non-requested fields excluded
                assert "Brand" not in item
                assert "PriceTier1" not in item
        finally:
            patcher.stop()

    async def test_pagination_next_offset(self):
        """nextOffset should be None when no more items, not None when more exist."""
        products = [{"SKU": f"P{i}", "Name": f"Product {i}"} for i in range(5)]
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": products, "Total": 5}),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            # Request first 3 items
            chunk1 = await cin7_products_snapshot_chunk(sid, offset=0, limit=3)
            assert len(chunk1["items"]) == 3
            assert chunk1["nextOffset"] is not None
            assert chunk1["nextOffset"] == 3

            # Request next chunk
            chunk2 = await cin7_products_snapshot_chunk(sid, offset=3, limit=3)
            assert len(chunk2["items"]) == 2
            assert chunk2["nextOffset"] is None
        finally:
            patcher.stop()

    async def test_close_cleans_up(self):
        """close should return ok=True and remove the snapshot from storage."""
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": [], "Total": 0}),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            close_result = await cin7_products_snapshot_close(sid)
            assert close_result["ok"] is True
            assert close_result["snapshotId"] == sid
            assert close_result["existed"] is True

            # Status should report not found after close
            status = await cin7_products_snapshot_status(sid)
            assert "error" in status
            assert status["error"] == "snapshot not found"
        finally:
            patcher.stop()

    async def test_not_found_returns_error(self):
        """status and chunk should return error for a non-existent snapshot ID."""
        status = await cin7_products_snapshot_status("nonexistent-id")
        assert status == {"error": "snapshot not found"}

        chunk = await cin7_products_snapshot_chunk("nonexistent-id", offset=0, limit=10)
        assert chunk == {"error": "snapshot not found"}

    async def test_multiple_pages_collected(self):
        """When list_products returns per_page items then an empty page, all items are collected."""
        page1 = [{"SKU": f"P{i}", "Name": f"Prod {i}"} for i in range(3)]
        page2 = [{"SKU": f"P{i}", "Name": f"Prod {i}"} for i in range(3, 5)]
        empty = []

        call_count = 0

        async def mock_list_products(page=1, limit=100, name=None, sku=None):
            nonlocal call_count
            call_count += 1
            if page == 1:
                return {"Products": page1, "Total": 5}
            elif page == 2:
                return {"Products": page2, "Total": 5}
            else:
                return {"Products": empty, "Total": 5}

        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(side_effect=mock_list_products),
        )
        try:
            # Use limit=3 so page1 has exactly per_page items, triggering next page
            start = await cin7_products_snapshot_start(limit=3)
            sid = start["snapshotId"]
            await asyncio.sleep(0.2)

            status = await cin7_products_snapshot_status(sid)
            assert status["ready"] is True
            assert status["total"] == 5

            chunk = await cin7_products_snapshot_chunk(sid, offset=0, limit=100)
            assert len(chunk["items"]) == 5
        finally:
            patcher.stop()


# ---------------------------------------------------------------------------
# Stock Snapshot Lifecycle
# ---------------------------------------------------------------------------


class TestStockSnapshotLifecycle:
    """Tests for the stock snapshot start / status / chunk / close flow."""

    async def test_start_returns_snapshot_id(self):
        """cin7_stock_snapshot_start should return a valid UUID snapshot ID."""
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": [], "Total": 0}
            ),
        )
        try:
            result = await cin7_stock_snapshot_start()
            assert "snapshotId" in result
            assert isinstance(result["snapshotId"], str)
            assert len(result["snapshotId"]) == 36
        finally:
            patcher.stop()

    async def test_status_returns_progress_after_build(self):
        """After the background task completes, status should show ready=True."""
        items = [
            {"SKU": "A", "Location": "Main", "OnHand": 10, "Available": 8, "Allocated": 2},
        ]
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": items, "Total": 1}
            ),
        )
        try:
            start = await cin7_stock_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            status = await cin7_stock_snapshot_status(sid)
            assert status["snapshotId"] == sid
            assert status["ready"] is True
            assert status["total"] == 1
            assert status["error"] is None
        finally:
            patcher.stop()

    async def test_chunk_with_default_projection(self):
        """Items should have default fields SKU, Location, OnHand, Available."""
        items = [
            {
                "SKU": "W-001",
                "Location": "Main",
                "OnHand": 50.0,
                "Available": 45.0,
                "Allocated": 5.0,
                "OnOrder": 10.0,
                "Bin": "A1",
                "Batch": "LOT1",
                "ProductID": "prod-123",
            },
        ]
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": items, "Total": 1}
            ),
        )
        try:
            start = await cin7_stock_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            chunk = await cin7_stock_snapshot_chunk(sid, offset=0, limit=10)
            assert len(chunk["items"]) == 1
            item = chunk["items"][0]
            # Default fields
            assert "SKU" in item
            assert "Location" in item
            assert "OnHand" in item
            assert "Available" in item
            # Non-requested fields excluded
            assert "Bin" not in item
            assert "Batch" not in item
            assert "ProductID" not in item
        finally:
            patcher.stop()

    async def test_extra_fields_included(self):
        """Requested fields like Allocated and Bin should be included in projection."""
        items = [
            {
                "SKU": "W-001",
                "Location": "Main",
                "OnHand": 50.0,
                "Available": 45.0,
                "Allocated": 5.0,
                "OnOrder": 10.0,
                "Bin": "A1",
                "Batch": "LOT1",
            },
        ]
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": items, "Total": 1}
            ),
        )
        try:
            start = await cin7_stock_snapshot_start(fields=["Allocated", "Bin"])
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            chunk = await cin7_stock_snapshot_chunk(sid, offset=0, limit=10)
            item = chunk["items"][0]
            assert item["Allocated"] == 5.0
            assert item["Bin"] == "A1"
            # Not requested
            assert "OnOrder" not in item
            assert "Batch" not in item
        finally:
            patcher.stop()

    async def test_close_cleans_up(self):
        """close should return ok=True and remove the snapshot."""
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": [], "Total": 0}
            ),
        )
        try:
            start = await cin7_stock_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            close_result = await cin7_stock_snapshot_close(sid)
            assert close_result["ok"] is True
            assert close_result["snapshotId"] == sid
            assert close_result["existed"] is True

            # Should be gone
            status = await cin7_stock_snapshot_status(sid)
            assert "error" in status
            assert status["error"] == "snapshot not found"
        finally:
            patcher.stop()

    async def test_not_found_returns_error(self):
        """status and chunk should return error for a bad snapshot ID."""
        status = await cin7_stock_snapshot_status("bad-id-999")
        assert status == {"error": "snapshot not found"}

        chunk = await cin7_stock_snapshot_chunk("bad-id-999", offset=0, limit=10)
        assert chunk == {"error": "snapshot not found"}


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestSnapshotEdgeCases:
    """Edge-case and boundary tests for both product and stock snapshots."""

    async def test_max_items_cap_respected(self):
        """Snapshot should stop collecting once SNAPSHOT_MAX_ITEMS is reached."""
        # Create a large batch that exceeds a small cap
        big_page = [{"SKU": f"P{i}", "Name": f"Prod {i}"} for i in range(20)]

        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": big_page, "Total": 20}),
        )
        original_max = server_mod.SNAPSHOT_MAX_ITEMS
        try:
            # Temporarily lower the cap
            server_mod.SNAPSHOT_MAX_ITEMS = 10
            start = await cin7_products_snapshot_start(limit=20)
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            status = await cin7_products_snapshot_status(sid)
            # The build should have stopped because 20 > 10
            assert status["error"] is not None
            assert "cap" in status["error"].lower()
            # Items should not exceed cap (the batch of 20 exceeded cap, so none were added)
            snap = server_mod._snapshots.get(sid)
            assert snap is not None
            assert len(snap.items) <= 10
        finally:
            server_mod.SNAPSHOT_MAX_ITEMS = original_max
            patcher.stop()

    async def test_multiple_snapshots_coexist(self):
        """Two snapshots started concurrently should have different IDs and independent data."""
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": [{"SKU": "X", "Name": "X"}], "Total": 1}),
        )
        try:
            start1 = await cin7_products_snapshot_start()
            start2 = await cin7_products_snapshot_start()

            assert start1["snapshotId"] != start2["snapshotId"]

            await asyncio.sleep(0.1)

            status1 = await cin7_products_snapshot_status(start1["snapshotId"])
            status2 = await cin7_products_snapshot_status(start2["snapshotId"])

            assert status1["snapshotId"] == start1["snapshotId"]
            assert status2["snapshotId"] == start2["snapshotId"]
            # Both should have completed independently
            assert status1["ready"] is True
            assert status2["ready"] is True
        finally:
            patcher.stop()

    async def test_build_error_captured(self):
        """If list_products raises an exception, snap.error should be set."""
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(side_effect=RuntimeError("API connection timeout")),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            status = await cin7_products_snapshot_status(sid)
            assert status["ready"] is False
            assert status["error"] is not None
            assert "API connection timeout" in status["error"]
        finally:
            patcher.stop()

    async def test_close_cancels_running_task(self):
        """Closing a snapshot that is still building should cancel the background task."""
        # Use a slow mock that will take a long time so the task is still running when we close
        async def slow_list(page=1, limit=100, name=None, sku=None):
            await asyncio.sleep(10)
            return {"Products": [], "Total": 0}

        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(side_effect=slow_list),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]

            # The task should still be running
            task = server_mod._snapshot_tasks.get(sid)
            assert task is not None
            assert not task.done()

            # Close should cancel it
            close_result = await cin7_products_snapshot_close(sid)
            assert close_result["ok"] is True
            assert close_result["existed"] is True

            # Give the event loop a moment to process the cancellation
            await asyncio.sleep(0.05)
            assert task.done()
            assert task.cancelled()
        finally:
            patcher.stop()


# ---------------------------------------------------------------------------
# TTL Expiry Tests
# ---------------------------------------------------------------------------

import time
from cin7_core_server.resources.snapshots import SNAPSHOT_TTL_SECONDS


class TestProductSnapshotTTLExpiry:
    """Tests that expired product snapshots are cleaned up on access."""

    async def test_expired_snapshot_cleaned_up_on_status_check(self):
        """An expired product snapshot should be removed when status is checked."""
        products = [{"SKU": "A", "Name": "Alpha"}]
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": products, "Total": 1}),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            # Manually expire the snapshot
            snap = server_mod._snapshots[sid]
            snap.created_at = time.time() - SNAPSHOT_TTL_SECONDS - 1

            # Status check triggers _cleanup_expired_snapshots()
            result = await cin7_products_snapshot_status(sid)
            assert result == {"error": "snapshot not found"}
        finally:
            patcher.stop()

    async def test_expired_snapshot_cleaned_up_on_chunk(self):
        """An expired product snapshot should be removed when chunk is requested."""
        products = [{"SKU": "A", "Name": "Alpha"}]
        patcher, _ = _mock_cin7_client(
            list_products=AsyncMock(return_value={"Products": products, "Total": 1}),
        )
        try:
            start = await cin7_products_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            # Manually expire the snapshot
            snap = server_mod._snapshots[sid]
            snap.created_at = time.time() - SNAPSHOT_TTL_SECONDS - 1

            # Chunk call triggers _cleanup_expired_snapshots()
            result = await cin7_products_snapshot_chunk(sid, offset=0)
            assert result == {"error": "snapshot not found"}
        finally:
            patcher.stop()


class TestStockSnapshotTTLExpiry:
    """Tests that expired stock snapshots are cleaned up on access."""

    async def test_expired_stock_snapshot_cleaned_up_on_status_check(self):
        """An expired stock snapshot should be removed when status is checked."""
        items = [{"SKU": "A", "Location": "Main", "OnHand": 10, "Available": 8}]
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": items, "Total": 1}
            ),
        )
        try:
            start = await cin7_stock_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            # Manually expire the snapshot
            snap = server_mod._stock_snapshots[sid]
            snap.created_at = time.time() - SNAPSHOT_TTL_SECONDS - 1

            # Status check triggers _cleanup_expired_stock_snapshots()
            result = await cin7_stock_snapshot_status(sid)
            assert result == {"error": "snapshot not found"}
        finally:
            patcher.stop()

    async def test_expired_stock_snapshot_cleaned_up_on_chunk(self):
        """An expired stock snapshot should be removed when chunk is requested."""
        items = [{"SKU": "A", "Location": "Main", "OnHand": 10, "Available": 8}]
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": items, "Total": 1}
            ),
        )
        try:
            start = await cin7_stock_snapshot_start()
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            # Manually expire the snapshot
            snap = server_mod._stock_snapshots[sid]
            snap.created_at = time.time() - SNAPSHOT_TTL_SECONDS - 1

            # Chunk call triggers _cleanup_expired_stock_snapshots()
            result = await cin7_stock_snapshot_chunk(sid, offset=0)
            assert result == {"error": "snapshot not found"}
        finally:
            patcher.stop()


# ---------------------------------------------------------------------------
# Stock Snapshot Max Items Cap
# ---------------------------------------------------------------------------


class TestStockSnapshotMaxItemsCap:
    """Tests that the stock snapshot respects the SNAPSHOT_MAX_ITEMS cap."""

    async def test_stock_max_items_cap_respected(self):
        """Stock snapshot should stop collecting once SNAPSHOT_MAX_ITEMS is reached."""
        big_page = [
            {"SKU": f"S{i}", "Location": "Main", "OnHand": float(i), "Available": float(i)}
            for i in range(20)
        ]
        patcher, _ = _mock_cin7_client(
            list_product_availability=AsyncMock(
                return_value={"ProductAvailabilityList": big_page, "Total": 20}
            ),
        )
        original_max = server_mod.SNAPSHOT_MAX_ITEMS
        try:
            # Temporarily lower the cap
            server_mod.SNAPSHOT_MAX_ITEMS = 10
            start = await cin7_stock_snapshot_start(limit=20)
            sid = start["snapshotId"]
            await asyncio.sleep(0.1)

            status = await cin7_stock_snapshot_status(sid)
            # The build should have stopped because 20 > 10
            assert status["error"] is not None
            assert "cap" in status["error"].lower()
            # Items should not exceed cap
            snap = server_mod._stock_snapshots.get(sid)
            assert snap is not None
            assert len(snap.items) <= 10
        finally:
            server_mod.SNAPSHOT_MAX_ITEMS = original_max
            patcher.stop()


# ---------------------------------------------------------------------------
# Close Non-Existent Snapshot
# ---------------------------------------------------------------------------


class TestSnapshotCloseNonExistent:
    """Tests that closing a non-existent snapshot returns existed=False."""

    async def test_product_close_nonexistent_returns_existed_false(self):
        """Closing a non-existent product snapshot should return ok=True, existed=False."""
        result = await cin7_products_snapshot_close("nonexistent-id")
        assert result["ok"] is True
        assert result["existed"] is False

    async def test_stock_close_nonexistent_returns_existed_false(self):
        """Closing a non-existent stock snapshot should return ok=True, existed=False."""
        result = await cin7_stock_snapshot_close("nonexistent-id")
        assert result["ok"] is True
        assert result["existed"] is False
