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
