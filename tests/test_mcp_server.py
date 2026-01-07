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
