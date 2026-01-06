"""Tests for Cin7 client methods."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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

    async def test_raises_without_sku_or_product_id(self, mock_client):
        """Should raise error if neither SKU nor product_id provided."""
        with pytest.raises(Cin7ClientError, match="requires product_id or sku"):
            await mock_client.get_product_availability()
