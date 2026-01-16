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


class TestSaveSale:
    """Tests for save_sale method."""

    async def test_creates_sale_successfully(self, mock_client):
        """Should create sale and return response data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"SaleID": "abc-123", "Customer": "Test Customer"}'
        mock_response.json.return_value = {
            "SaleID": "abc-123",
            "Customer": "Test Customer",
            "Status": "DRAFT"
        }
        mock_client.client.post = AsyncMock(return_value=mock_response)

        payload = {
            "Customer": "Test Customer",
            "Location": "MAIN",
            "Lines": [
                {
                    "ProductID": "prod-123",
                    "SKU": "TEST-SKU",
                    "Name": "Test Product",
                    "Quantity": 1,
                    "Price": 10.0,
                    "Tax": 0,
                    "TaxRule": "Tax Exempt",
                    "Total": 10.0
                }
            ]
        }
        result = await mock_client.save_sale(payload)

        assert result["SaleID"] == "abc-123"
        assert result["Customer"] == "Test Customer"
        mock_client.client.post.assert_called_once()
        call_args = mock_client.client.post.call_args
        # Verify the payload was passed
        assert "Sale" in call_args[0] or call_args[1].get("json") is not None

    async def test_defaults_status_to_draft(self, mock_client):
        """Should set Status to DRAFT if not provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"SaleID": "abc-123"}'
        mock_response.json.return_value = {"SaleID": "abc-123"}
        mock_client.client.post = AsyncMock(return_value=mock_response)

        payload = {"Customer": "Test", "Location": "MAIN", "Lines": []}
        await mock_client.save_sale(payload)

        call_args = mock_client.client.post.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload.get("Status") == "DRAFT"

    async def test_preserves_authorised_status(self, mock_client):
        """Should preserve AUTHORISED status if explicitly set."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"SaleID": "abc-123"}'
        mock_response.json.return_value = {"SaleID": "abc-123"}
        mock_client.client.post = AsyncMock(return_value=mock_response)

        payload = {"Customer": "Test", "Location": "MAIN", "Lines": [], "Status": "AUTHORISED"}
        await mock_client.save_sale(payload)

        call_args = mock_client.client.post.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload.get("Status") == "AUTHORISED"

    async def test_raises_on_api_error(self, mock_client):
        """Should raise Cin7ClientError on non-2xx response."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Customer is required"
        mock_response.json.return_value = {"error": "Customer is required"}
        mock_client.client.post = AsyncMock(return_value=mock_response)

        payload = {"Location": "MAIN", "Lines": []}
        with pytest.raises(Cin7ClientError, match="Sale save error"):
            await mock_client.save_sale(payload)


class TestUpdateSale:
    """Tests for update_sale method."""

    async def test_updates_sale_successfully(self, mock_client):
        """Should update sale and return response data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"SaleID": "abc-123", "Customer": "Updated Customer"}'
        mock_response.json.return_value = {
            "SaleID": "abc-123",
            "Customer": "Updated Customer"
        }
        mock_client.client.put = AsyncMock(return_value=mock_response)

        payload = {
            "SaleID": "abc-123",
            "Customer": "Updated Customer",
            "Location": "MAIN"
        }
        result = await mock_client.update_sale(payload)

        assert result["SaleID"] == "abc-123"
        assert result["Customer"] == "Updated Customer"
        mock_client.client.put.assert_called_once()

    async def test_raises_on_api_error(self, mock_client):
        """Should raise Cin7ClientError on non-2xx response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Sale not found"
        mock_response.json.return_value = {"error": "Sale not found"}
        mock_client.client.put = AsyncMock(return_value=mock_response)

        payload = {"SaleID": "nonexistent", "Customer": "Test"}
        with pytest.raises(Cin7ClientError, match="Sale update error"):
            await mock_client.update_sale(payload)


class TestSavePurchaseOrder:
    """Tests for save_purchase_order method (two-step process)."""

    async def test_creates_purchase_with_lines_two_step(self, mock_client):
        """Should create purchase header then add order lines in two API calls."""
        # Step 1: POST /Purchase returns TaskID
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "task-123", "Supplier": "Test Supplier"}'
        header_response.json.return_value = {
            "ID": "task-123",
            "Supplier": "Test Supplier",
            "Status": "DRAFT"
        }

        # Step 2: POST /purchase/order returns order with lines
        order_response = MagicMock()
        order_response.status_code = 200
        order_response.text = '{"TaskID": "task-123", "Status": "DRAFT", "Lines": [...]}'
        order_response.json.return_value = {
            "TaskID": "task-123",
            "Status": "DRAFT",
            "Lines": [
                {"ProductID": "prod-123", "SKU": "TEST-SKU", "Quantity": 5}
            ]
        }

        # Mock post to return different responses for each call
        mock_client.client.post = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Supplier": "Test Supplier",
            "Location": "MAIN",
            "Lines": [
                {
                    "ProductID": "prod-123",
                    "SKU": "TEST-SKU",
                    "Name": "Test Product",
                    "Quantity": 5,
                    "Price": 10.0,
                    "Tax": 0,
                    "TaxRule": "Tax Exempt",
                    "Total": 50.0
                }
            ]
        }
        result = await mock_client.save_purchase_order(payload)

        # Should have made two POST calls
        assert mock_client.client.post.call_count == 2

        # First call: POST /Purchase (header only, no Lines)
        first_call = mock_client.client.post.call_args_list[0]
        assert first_call[0][0] == "Purchase"
        first_payload = first_call.kwargs.get("json", first_call[1].get("json", {}))
        assert "Lines" not in first_payload
        assert first_payload.get("Supplier") == "Test Supplier"

        # Second call: POST /purchase/order with TaskID and Lines
        second_call = mock_client.client.post.call_args_list[1]
        assert second_call[0][0] == "purchase/order"
        second_payload = second_call.kwargs.get("json", second_call[1].get("json", {}))
        assert second_payload.get("TaskID") == "task-123"
        assert "Lines" in second_payload
        assert len(second_payload["Lines"]) == 1

        # Result should include Order data
        assert result["ID"] == "task-123"
        assert "Order" in result

    async def test_creates_purchase_without_lines_single_step(self, mock_client):
        """Should create purchase header only if no lines provided."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "task-123", "Supplier": "Test Supplier"}'
        header_response.json.return_value = {
            "ID": "task-123",
            "Supplier": "Test Supplier",
            "Status": "DRAFT"
        }
        mock_client.client.post = AsyncMock(return_value=header_response)

        payload = {
            "Supplier": "Test Supplier",
            "Location": "MAIN"
        }
        result = await mock_client.save_purchase_order(payload)

        # Should only make one POST call
        assert mock_client.client.post.call_count == 1
        assert result["ID"] == "task-123"

    async def test_defaults_status_to_draft(self, mock_client):
        """Should set Status to DRAFT if not provided."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "task-123"}'
        header_response.json.return_value = {"ID": "task-123"}
        mock_client.client.post = AsyncMock(return_value=header_response)

        payload = {"Supplier": "Test", "Location": "MAIN"}
        await mock_client.save_purchase_order(payload)

        call_args = mock_client.client.post.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload.get("Status") == "DRAFT"

    async def test_raises_on_header_creation_error(self, mock_client):
        """Should raise Cin7ClientError if header creation fails."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Supplier is required"
        mock_response.json.return_value = {"error": "Supplier is required"}
        mock_client.client.post = AsyncMock(return_value=mock_response)

        payload = {"Location": "MAIN", "Lines": [{"ProductID": "123"}]}
        with pytest.raises(Cin7ClientError, match="header creation error"):
            await mock_client.save_purchase_order(payload)

    async def test_raises_on_order_lines_creation_error(self, mock_client):
        """Should raise Cin7ClientError if order lines creation fails."""
        # Step 1 succeeds
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "task-123"}'
        header_response.json.return_value = {"ID": "task-123"}

        # Step 2 fails
        order_response = MagicMock()
        order_response.status_code = 400
        order_response.text = "Bad Request: Invalid product"
        order_response.json.return_value = {"error": "Invalid product"}

        mock_client.client.post = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Supplier": "Test",
            "Location": "MAIN",
            "Lines": [{"ProductID": "invalid"}]
        }
        with pytest.raises(Cin7ClientError, match="lines creation error"):
            await mock_client.save_purchase_order(payload)

    async def test_raises_if_no_task_id_returned(self, mock_client):
        """Should raise Cin7ClientError if no TaskID returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"Supplier": "Test"}'
        mock_response.json.return_value = {"Supplier": "Test"}  # No ID field
        mock_client.client.post = AsyncMock(return_value=mock_response)

        payload = {"Supplier": "Test", "Location": "MAIN", "Lines": [{"ProductID": "123"}]}
        with pytest.raises(Cin7ClientError, match="No TaskID returned"):
            await mock_client.save_purchase_order(payload)
