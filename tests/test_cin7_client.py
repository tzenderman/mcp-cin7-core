"""Tests for Cin7 client methods."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cin7_core_server.cin7_client import Cin7Client, Cin7ClientError

from tests.fixtures.common import (
    ME_RESPONSE,
    HEALTH_CHECK_RESPONSE,
    ERROR_AUTH_401,
    ERROR_BAD_REQUEST_400,
)
from tests.fixtures.products import (
    PRODUCT_LIST_RESPONSE,
    PRODUCT_SINGLE,
    PRODUCT_EMPTY_LIST,
    PRODUCT_SAVE_RESPONSE,
    PRODUCT_UPDATE_RESPONSE,
    PRODUCT_SUPPLIERS_RESPONSE,
    PRODUCT_SUPPLIERS_UPDATE_RESPONSE,
)
from tests.fixtures.suppliers import (
    SUPPLIER_LIST_RESPONSE,
    SUPPLIER_SINGLE,
    SUPPLIER_EMPTY_LIST,
    SUPPLIER_SAVE_RESPONSE,
    SUPPLIER_UPDATE_RESPONSE,
)
from tests.fixtures.sales import (
    SALE_LIST_RESPONSE,
    SALE_SINGLE,
    SALE_HEADER_RESPONSE,
    SALE_ORDER_RESPONSE,
)
from tests.fixtures.purchase_orders import (
    PO_LIST_RESPONSE,
    PO_SINGLE,
    PO_HEADER_RESPONSE,
    PO_ORDER_RESPONSE,
)
from tests.fixtures.stock import (
    STOCK_AVAILABILITY_LIST,
    STOCK_SINGLE_SKU_MULTI_LOCATION,
)
from tests.fixtures.stock_transfers import (
    STOCK_TRANSFER_LIST_RESPONSE,
    STOCK_TRANSFER_SINGLE,
    STOCK_TRANSFER_NOT_FOUND_400,
)


# ---------------------------------------------------------------------------
# TestFromEnv
# ---------------------------------------------------------------------------


class TestFromEnv:
    """Tests for Cin7Client.from_env class method."""

    async def test_success(self):
        """Should create client with valid env vars."""
        with patch.dict("os.environ", {
            "CIN7_ACCOUNT_ID": "my_account",
            "CIN7_API_KEY": "my_key",
        }, clear=False):
            client = Cin7Client.from_env()
            assert client.account_id == "my_account"
            assert client.application_key == "my_key"
            assert client.base_url.endswith("/")


    async def test_missing_account_id(self):
        """Should raise Cin7ClientError when CIN7_ACCOUNT_ID is missing."""
        with patch.dict("os.environ", {"CIN7_API_KEY": "my_key"}, clear=True):
            with pytest.raises(Cin7ClientError, match="Missing CIN7_ACCOUNT_ID or CIN7_API_KEY"):
                Cin7Client.from_env()

    async def test_missing_api_key(self):
        """Should raise Cin7ClientError when CIN7_API_KEY is missing."""
        with patch.dict("os.environ", {"CIN7_ACCOUNT_ID": "my_account"}, clear=True):
            with pytest.raises(Cin7ClientError, match="Missing CIN7_ACCOUNT_ID or CIN7_API_KEY"):
                Cin7Client.from_env()

    async def test_custom_base_url(self):
        """Should use custom CIN7_BASE_URL when provided."""
        with patch.dict("os.environ", {
            "CIN7_ACCOUNT_ID": "my_account",
            "CIN7_API_KEY": "my_key",
            "CIN7_BASE_URL": "https://custom.api.com/v2",
        }, clear=False):
            client = Cin7Client.from_env()
            assert client.base_url == "https://custom.api.com/v2/"


    async def test_default_base_url(self):
        """Should use default DEAR base URL when CIN7_BASE_URL is not set."""
        with patch.dict("os.environ", {
            "CIN7_ACCOUNT_ID": "my_account",
            "CIN7_API_KEY": "my_key",
        }, clear=False):
            # Remove CIN7_BASE_URL if it happens to be set
            import os
            env_copy = {
                "CIN7_ACCOUNT_ID": "my_account",
                "CIN7_API_KEY": "my_key",
            }
            with patch.dict("os.environ", env_copy, clear=True):
                client = Cin7Client.from_env()
                assert client.base_url == "https://inventory.dearsystems.com/ExternalApi/v2/"
    


# ---------------------------------------------------------------------------
# TestHealthCheck
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for health_check method."""

    async def test_success_returns_ok_status_sample_count(self, mock_client):
        """Should return ok, status, and sample_count on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = HEALTH_CHECK_RESPONSE
        mock_resp.text = str(HEALTH_CHECK_RESPONSE)
        mock_resp.headers = {"X-RateLimit-Remaining": "95"}
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.health_check()

        assert result["ok"] is True
        assert result["status"] == 200
        assert result["sample_count"] == 1
        assert result["rate_limit_remaining"] == "95"
        mock_client._request.assert_called_once()

    async def test_auth_failure_401_raises(self, mock_client):
        """Should raise Cin7ClientError on 401 auth failure."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "Unauthorized"}
        mock_resp.text = ERROR_AUTH_401
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Cin7 Core auth failed or API error"):
            await mock_client.health_check()

    async def test_server_error_500_raises(self, mock_client):
        """Should raise Cin7ClientError on 500 server error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Internal Server Error"}
        mock_resp.text = "Internal Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Cin7 Core auth failed or API error"):
            await mock_client.health_check()


# ---------------------------------------------------------------------------
# TestGetMe
# ---------------------------------------------------------------------------


class TestGetMe:
    """Tests for get_me method."""

    async def test_success_returns_dict(self, mock_client):
        """Should return account info dict on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ME_RESPONSE
        mock_resp.text = str(ME_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_me()

        assert result["Company"] == "Acme Corp"
        assert result["Currency"] == "USD"
        mock_client._request.assert_called_once_with("get", "me")

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": "Forbidden"}
        mock_resp.text = "Forbidden"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Me endpoint error"):
            await mock_client.get_me()


# ---------------------------------------------------------------------------
# TestListProducts
# ---------------------------------------------------------------------------


class TestListProducts:
    """Tests for list_products method."""

    async def test_success(self, mock_client):
        """Should return product list on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_LIST_RESPONSE
        mock_resp.text = str(PRODUCT_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.list_products()

        assert "Products" in result
        assert len(result["Products"]) == 2
        assert result["Total"] == 2

    async def test_name_filter_passes_name_param(self, mock_client):
        """Should pass Name param when name filter provided."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_LIST_RESPONSE
        mock_resp.text = str(PRODUCT_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.list_products(name="Widget")

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Name"] == "Widget"

    async def test_sku_filter_passes_sku_param(self, mock_client):
        """Should pass Sku param when sku filter provided.

        API docs: GET /Product uses 'Sku' (not 'SKU') as the query param name.
        See: https://dearinventory.docs.apiary.io/#reference/product/product/get
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_LIST_RESPONSE
        mock_resp.text = str(PRODUCT_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.list_products(sku="WIDGET-001")

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params.get("Sku") == "WIDGET-001", "API docs use 'Sku' not 'SKU'"
        assert "SKU" not in params, "Must not send 'SKU' — API param is 'Sku'"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Product list error"):
            await mock_client.list_products()


# ---------------------------------------------------------------------------
# TestGetProduct
# ---------------------------------------------------------------------------


class TestGetProduct:
    """Tests for get_product method."""

    async def test_by_id(self, mock_client):
        """Should pass ID param and return first product from Products list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Products": [PRODUCT_SINGLE], "Total": 1}
        mock_resp.text = str({"Products": [PRODUCT_SINGLE]})
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_product(product_id="prod-abc-123")

        assert result["ID"] == "prod-abc-123"
        assert result["SKU"] == "WIDGET-001"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["ID"] == "prod-abc-123"

    async def test_by_sku(self, mock_client):
        """Should pass Sku param and return first product.

        API docs: GET /Product uses 'Sku' (not 'SKU') as the query param name.
        See: https://dearinventory.docs.apiary.io/#reference/product/product/get
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Products": [PRODUCT_SINGLE], "Total": 1}
        mock_resp.text = str({"Products": [PRODUCT_SINGLE]})
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_product(sku="WIDGET-001")

        assert result["SKU"] == "WIDGET-001"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params.get("Sku") == "WIDGET-001", "API docs use 'Sku' not 'SKU'"
        assert "SKU" not in params, "Must not send 'SKU' — API param is 'Sku'"

    async def test_not_found_empty_products_returns_data(self, mock_client):
        """When Products list is empty but data dict is truthy, returns the data dict."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_EMPTY_LIST
        mock_resp.text = str(PRODUCT_EMPTY_LIST)
        mock_client._request = AsyncMock(return_value=mock_resp)

        # PRODUCT_EMPTY_LIST is {"Products": [], "Total": 0} which is truthy
        result = await mock_client.get_product(product_id="nonexistent")
        assert result == PRODUCT_EMPTY_LIST

    async def test_no_params_raises_value_error(self, mock_client):
        """Should raise Cin7ClientError if neither product_id nor sku provided."""
        with pytest.raises(Cin7ClientError, match="get_product requires product_id or sku"):
            await mock_client.get_product()

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Product get error"):
            await mock_client.get_product(product_id="prod-abc-123")


# ---------------------------------------------------------------------------
# TestSaveProduct
# ---------------------------------------------------------------------------


class TestSaveProduct:
    """Tests for save_product method."""

    async def test_success_200(self, mock_client):
        """Should return product data on 200 response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_SAVE_RESPONSE
        mock_resp.text = str(PRODUCT_SAVE_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        payload = {"SKU": "NEWPROD-001", "Name": "New Product", "Category": "Test"}
        result = await mock_client.save_product(payload)

        assert result["ID"] == "prod-new-789"
        assert result["SKU"] == "NEWPROD-001"
        mock_client._request.assert_called_once_with("post", "Product", json=payload)

    async def test_success_201(self, mock_client):
        """Should return product data on 201 created response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = PRODUCT_SAVE_RESPONSE
        mock_resp.text = str(PRODUCT_SAVE_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        payload = {"SKU": "NEWPROD-001", "Name": "New Product"}
        result = await mock_client.save_product(payload)

        assert result["ID"] == "prod-new-789"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Bad Request"}
        mock_resp.text = ERROR_BAD_REQUEST_400
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Product save error"):
            await mock_client.save_product({"SKU": "BAD"})


# ---------------------------------------------------------------------------
# TestUpdateProduct
# ---------------------------------------------------------------------------


class TestUpdateProduct:
    """Tests for update_product method."""

    async def test_success_200(self, mock_client):
        """Should return updated product data on 200 response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_UPDATE_RESPONSE
        mock_resp.text = str(PRODUCT_UPDATE_RESPONSE)
        mock_resp.headers = {}
        mock_client._request = AsyncMock(return_value=mock_resp)

        payload = {"ID": "prod-abc-123", "Name": "Updated Widget"}
        result = await mock_client.update_product(payload)

        assert result["Name"] == "Updated Widget"
        mock_client._request.assert_called_once_with("put", "Product", json=payload)

    async def test_success_204(self, mock_client):
        """Should return data on 204 no-content response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.json.return_value = PRODUCT_UPDATE_RESPONSE
        mock_resp.text = str(PRODUCT_UPDATE_RESPONSE)
        mock_resp.headers = {}
        mock_client._request = AsyncMock(return_value=mock_resp)

        payload = {"ID": "prod-abc-123", "Name": "Updated Widget"}
        result = await mock_client.update_product(payload)

        assert result["ID"] == "prod-abc-123"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Bad Request"}
        mock_resp.text = ERROR_BAD_REQUEST_400
        mock_resp.headers = {}
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Product update error"):
            await mock_client.update_product({"ID": "prod-abc-123"})


# ---------------------------------------------------------------------------
# TestListSuppliers
# ---------------------------------------------------------------------------


class TestListSuppliers:
    """Tests for list_suppliers method."""

    async def test_success(self, mock_client):
        """Should return supplier list on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_LIST_RESPONSE
        mock_resp.text = str(SUPPLIER_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.list_suppliers()

        assert "SupplierList" in result
        assert len(result["SupplierList"]) == 2
        assert result["Total"] == 2

    async def test_name_filter(self, mock_client):
        """Should pass Name param when name filter provided."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_LIST_RESPONSE
        mock_resp.text = str(SUPPLIER_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.list_suppliers(name="Acme")

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Name"] == "Acme"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Supplier list error"):
            await mock_client.list_suppliers()


# ---------------------------------------------------------------------------
# TestGetSupplier
# ---------------------------------------------------------------------------


class TestGetSupplier:
    """Tests for get_supplier method."""

    async def test_by_id(self, mock_client):
        """Should pass ID param and return first supplier from SupplierList."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_LIST_RESPONSE
        mock_resp.text = str(SUPPLIER_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_supplier(supplier_id="sup-abc-123")

        assert result["ID"] == "sup-abc-123"
        assert result["Name"] == "Acme Supplies"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["ID"] == "sup-abc-123"

    async def test_by_name(self, mock_client):
        """Should pass Name param and return first supplier."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_LIST_RESPONSE
        mock_resp.text = str(SUPPLIER_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_supplier(name="Acme Supplies")

        assert result["Name"] == "Acme Supplies"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Name"] == "Acme Supplies"

    async def test_not_found_empty_list_returns_data(self, mock_client):
        """When SupplierList is empty but data dict is truthy, returns data dict."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_EMPTY_LIST
        mock_resp.text = str(SUPPLIER_EMPTY_LIST)
        mock_client._request = AsyncMock(return_value=mock_resp)

        # SUPPLIER_EMPTY_LIST is {"SupplierList": [], "Total": 0} which is truthy
        result = await mock_client.get_supplier(supplier_id="nonexistent")
        assert result == SUPPLIER_EMPTY_LIST

    async def test_no_params_raises_error(self, mock_client):
        """Should raise Cin7ClientError if neither supplier_id nor name provided."""
        with pytest.raises(Cin7ClientError, match="get_supplier requires supplier_id or name"):
            await mock_client.get_supplier()

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Supplier get error"):
            await mock_client.get_supplier(supplier_id="sup-abc-123")


# ---------------------------------------------------------------------------
# TestSaveSupplier
# ---------------------------------------------------------------------------


class TestSaveSupplier:
    """Tests for save_supplier method."""

    async def test_success(self, mock_client):
        """Should return supplier data on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_SAVE_RESPONSE
        mock_resp.text = str(SUPPLIER_SAVE_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        payload = {"Name": "New Supplier", "ContactPerson": "Bob Wilson"}
        result = await mock_client.save_supplier(payload)

        assert result["ID"] == "sup-new-789"
        assert result["Name"] == "New Supplier"
        mock_client._request.assert_called_once_with("post", "Supplier", json=payload)

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Bad Request"}
        mock_resp.text = ERROR_BAD_REQUEST_400
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Supplier save error"):
            await mock_client.save_supplier({"Name": "Bad"})


# ---------------------------------------------------------------------------
# TestUpdateSupplier
# ---------------------------------------------------------------------------


class TestUpdateSupplier:
    """Tests for update_supplier method."""

    async def test_success(self, mock_client):
        """Should return updated supplier data on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SUPPLIER_UPDATE_RESPONSE
        mock_resp.text = str(SUPPLIER_UPDATE_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        payload = {"ID": "sup-abc-123", "Name": "Acme Supplies Updated"}
        result = await mock_client.update_supplier(payload)

        assert result["Name"] == "Acme Supplies Updated"
        mock_client._request.assert_called_once_with("put", "Supplier", json=payload)

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Bad Request"}
        mock_resp.text = ERROR_BAD_REQUEST_400
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Supplier update error"):
            await mock_client.update_supplier({"ID": "sup-abc-123"})


# ---------------------------------------------------------------------------
# TestListSales
# ---------------------------------------------------------------------------


class TestListSales:
    """Tests for list_sales method."""

    async def test_success(self, mock_client):
        """Should return sale list on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SALE_LIST_RESPONSE
        mock_resp.text = str(SALE_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.list_sales()

        assert "SaleList" in result
        assert len(result["SaleList"]) == 2
        assert result["Total"] == 2

    async def test_search_filter(self, mock_client):
        """Should pass Search param when search filter provided."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SALE_LIST_RESPONSE
        mock_resp.text = str(SALE_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.list_sales(search="Test Customer")

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Search"] == "Test Customer"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Sale list error"):
            await mock_client.list_sales()


# ---------------------------------------------------------------------------
# TestGetSale
# ---------------------------------------------------------------------------


class TestGetSale:
    """Tests for get_sale method."""

    async def test_success(self, mock_client):
        """Should return sale data on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SALE_SINGLE
        mock_resp.text = str(SALE_SINGLE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_sale(sale_id="sale-abc-123")

        assert result["ID"] == "sale-abc-123"
        assert result["Customer"] == "Test Customer"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["ID"] == "sale-abc-123"

    async def test_optional_params_forwarded(self, mock_client):
        """Should forward optional boolean params to API when set to True."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SALE_SINGLE
        mock_resp.text = str(SALE_SINGLE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.get_sale(
            sale_id="sale-abc-123",
            combine_additional_charges=True,
            hide_inventory_movements=True,
            include_transactions=True,
        )

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["CombineAdditionalCharges"] == "true"
        assert params["HideInventoryMovements"] == "true"
        assert params["IncludeTransactions"] == "true"

    async def test_no_sale_id_raises(self, mock_client):
        """Should raise Cin7ClientError if sale_id not provided."""
        with pytest.raises(Cin7ClientError, match="get_sale requires sale_id"):
            await mock_client.get_sale()

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"error": "Not Found"}
        mock_resp.text = "Not Found"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Sale get error"):
            await mock_client.get_sale(sale_id="nonexistent")


# ---------------------------------------------------------------------------
# TestListPurchaseOrders
# ---------------------------------------------------------------------------


class TestListPurchaseOrders:
    """Tests for list_purchase_orders method."""

    async def test_success(self, mock_client):
        """Should return purchase order list on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PO_LIST_RESPONSE
        mock_resp.text = str(PO_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.list_purchase_orders()

        assert "PurchaseList" in result
        assert len(result["PurchaseList"]) == 2
        assert result["Total"] == 2

    async def test_search_filter(self, mock_client):
        """Should pass Search param when search filter provided."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PO_LIST_RESPONSE
        mock_resp.text = str(PO_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.list_purchase_orders(search="Acme")

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Search"] == "Acme"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Purchase Order list error"):
            await mock_client.list_purchase_orders()


# ---------------------------------------------------------------------------
# TestGetPurchaseOrder
# ---------------------------------------------------------------------------


class TestGetPurchaseOrder:
    """Tests for get_purchase_order method."""

    async def test_success_returns_first_from_purchase_list(self, mock_client):
        """Should return first item from PurchaseList in response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"PurchaseList": [PO_SINGLE], "Total": 1}
        mock_resp.text = str({"PurchaseList": [PO_SINGLE]})
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_purchase_order(purchase_order_id="po-abc-123")

        assert result["ID"] == "po-abc-123"
        assert result["Supplier"] == "Acme Supplies"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["ID"] == "po-abc-123"

    async def test_not_found_empty_purchase_list_returns_data(self, mock_client):
        """When PurchaseList is empty but data dict is truthy, returns data dict."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        empty_response = {"PurchaseList": [], "Total": 0}
        mock_resp.json.return_value = empty_response
        mock_resp.text = str(empty_response)
        mock_client._request = AsyncMock(return_value=mock_resp)

        # The data dict is truthy so it falls through to return data
        result = await mock_client.get_purchase_order(purchase_order_id="nonexistent")
        assert result == empty_response

    async def test_no_id_raises(self, mock_client):
        """Should raise Cin7ClientError if purchase_order_id not provided."""
        with pytest.raises(Cin7ClientError, match="get_purchase_order requires purchase_order_id"):
            await mock_client.get_purchase_order()

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Purchase Order get error"):
            await mock_client.get_purchase_order(purchase_order_id="po-abc-123")


# ---------------------------------------------------------------------------
# TestListStockTransfers
# ---------------------------------------------------------------------------


class TestListStockTransfers:
    """Tests for list_stock_transfers method."""

    async def test_success(self, mock_client):
        """Should return stock transfer list on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = STOCK_TRANSFER_LIST_RESPONSE
        mock_resp.text = str(STOCK_TRANSFER_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.list_stock_transfers()

        assert "StockTransferList" in result
        assert len(result["StockTransferList"]) == 2
        assert result["Total"] == 2

    async def test_search_filter(self, mock_client):
        """Should pass Search param when search filter provided."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = STOCK_TRANSFER_LIST_RESPONSE
        mock_resp.text = str(STOCK_TRANSFER_LIST_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        await mock_client.list_stock_transfers(search="Main Warehouse")

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Search"] == "Main Warehouse"

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Stock Transfer list error"):
            await mock_client.list_stock_transfers()


# ---------------------------------------------------------------------------
# TestGetStockTransfer
# ---------------------------------------------------------------------------


class TestGetStockTransfer:
    """Tests for get_stock_transfer method."""

    async def test_success_returns_first_from_list(self, mock_client):
        """Should return first item from StockTransferList in response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "StockTransferList": [STOCK_TRANSFER_SINGLE],
            "Total": 1,
        }
        mock_resp.text = str({"StockTransferList": [STOCK_TRANSFER_SINGLE]})
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_stock_transfer(stock_transfer_id="st-task-001")

        assert result["TaskID"] == "st-task-001"
        assert result["FromLocation"] == "Main Warehouse"
        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["TaskID"] == "st-task-001"

    async def test_400_not_found_raises_stock_transfer_not_found(self, mock_client):
        """Should raise 'Stock Transfer not found' on 400 with not-found Exception."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = STOCK_TRANSFER_NOT_FOUND_400
        mock_resp.text = str(STOCK_TRANSFER_NOT_FOUND_400)
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Stock Transfer not found"):
            await mock_client.get_stock_transfer(stock_transfer_id="st-nonexistent")

    async def test_generic_400_raises(self, mock_client):
        """Should raise generic error on 400 without not-found message."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = [{"Exception": "Some other error"}]
        mock_resp.text = "Some other error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Stock Transfer get error"):
            await mock_client.get_stock_transfer(stock_transfer_id="st-bad")

    async def test_no_id_raises(self, mock_client):
        """Should raise Cin7ClientError if stock_transfer_id not provided."""
        with pytest.raises(Cin7ClientError, match="get_stock_transfer requires stock_transfer_id"):
            await mock_client.get_stock_transfer()

    async def test_api_error_500_raises(self, mock_client):
        """Should raise Cin7ClientError on 500 server error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="Stock Transfer get error"):
            await mock_client.get_stock_transfer(stock_transfer_id="st-task-001")


# ---------------------------------------------------------------------------
# TestGetProductSuppliers
# ---------------------------------------------------------------------------


class TestGetProductSuppliers:
    """Tests for get_product_suppliers method."""

    async def test_by_id(self, mock_client):
        """Should pass ProductID param and return product suppliers data.

        API docs: GET /product-suppliers uses 'ProductID' (Guid) as the query param.
        See: https://dearinventory.docs.apiary.io/#reference/reference-books/product-suppliers/get
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_SUPPLIERS_RESPONSE
        mock_resp.text = str(PRODUCT_SUPPLIERS_RESPONSE)
        mock_client._request = AsyncMock(return_value=mock_resp)

        result = await mock_client.get_product_suppliers(product_id="prod-abc-123")

        assert "Products" in result
        assert result["Products"][0]["ProductID"] == "prod-abc-123"
        call_args = mock_client._request.call_args
        assert call_args[0][1] == "product-suppliers", "API path must be 'product-suppliers'"
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params.get("ProductID") == "prod-abc-123", "API param is 'ProductID' not 'ID'"
        assert "ID" not in params, "Must not send 'ID' — API param is 'ProductID'"

    async def test_no_params_raises(self, mock_client):
        """Should raise TypeError when product_id is not provided (required argument)."""
        with pytest.raises(TypeError):
            await mock_client.get_product_suppliers()

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Server Error"}
        mock_resp.text = "Server Error"
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="ProductSuppliers get error"):
            await mock_client.get_product_suppliers(product_id="prod-abc-123")


# ---------------------------------------------------------------------------
# TestUpdateProductSuppliers
# ---------------------------------------------------------------------------


class TestUpdateProductSuppliers:
    """Tests for update_product_suppliers method."""

    async def test_success(self, mock_client):
        """Should return updated product suppliers data on success."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = PRODUCT_SUPPLIERS_UPDATE_RESPONSE
        mock_resp.text = str(PRODUCT_SUPPLIERS_UPDATE_RESPONSE)
        mock_resp.headers = {}
        mock_client._request = AsyncMock(return_value=mock_resp)

        products = [
            {
                "ProductID": "prod-abc-123",
                "Suppliers": [
                    {"SupplierID": "sup-222", "SupplierName": "New Supplier", "Cost": 10.00}
                ],
            }
        ]
        result = await mock_client.update_product_suppliers(products)

        assert "Products" in result
        assert result["Products"][0]["Suppliers"][0]["SupplierName"] == "New Supplier"
        call_args = mock_client._request.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload == {"Products": products}

    async def test_api_error_raises(self, mock_client):
        """Should raise Cin7ClientError on API error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error": "Bad Request"}
        mock_resp.text = ERROR_BAD_REQUEST_400
        mock_resp.headers = {}
        mock_client._request = AsyncMock(return_value=mock_resp)

        with pytest.raises(Cin7ClientError, match="ProductSuppliers update error"):
            await mock_client.update_product_suppliers([{"ProductID": "bad"}])


# ---------------------------------------------------------------------------
# TestListProductAvailability (preserved from existing tests)
# ---------------------------------------------------------------------------


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
        mock_client._request = AsyncMock(return_value=mock_response)

        result = await mock_client.list_product_availability(page=1, limit=100)

        assert "ProductAvailabilityList" in result
        assert len(result["ProductAvailabilityList"]) == 1
        assert result["ProductAvailabilityList"][0]["SKU"] == "TEST-001"
        mock_client._request.assert_called_once()

    async def test_passes_filter_params(self, mock_client):
        """Should pass SKU and location filters to API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ProductAvailabilityList": [], "Total": 0}
        mock_client._request = AsyncMock(return_value=mock_response)

        await mock_client.list_product_availability(
            page=2, limit=50, sku="TEST-001", location="Main"
        )

        call_args = mock_client._request.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["Page"] == 2
        assert params["Limit"] == 50
        assert params.get("Sku") == "TEST-001", "API docs use 'Sku' not 'SKU'"
        assert "SKU" not in params, "Must not send 'SKU' — API param is 'Sku'"
        assert params["Location"] == "Main"


# ---------------------------------------------------------------------------
# TestGetProductAvailability (preserved from existing tests)
# ---------------------------------------------------------------------------


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
        mock_client._request = AsyncMock(return_value=mock_response)

        result = await mock_client.get_product_availability(sku="TEST-001")

        assert len(result) == 2
        assert result[0]["Location"] == "Main"
        assert result[1]["Location"] == "Store"

    async def test_raises_without_sku_or_product_id(self, mock_client):
        """Should raise error if neither SKU nor product_id provided."""
        with pytest.raises(Cin7ClientError, match="requires product_id or sku"):
            await mock_client.get_product_availability()


# ---------------------------------------------------------------------------
# TestSaveSale (preserved from existing tests)
# ---------------------------------------------------------------------------


class TestSaveSale:
    """Tests for save_sale method (two-step process)."""

    async def test_creates_sale_with_lines_two_step(self, mock_client):
        """Should create sale header then add order lines in two API calls."""
        # Step 1: POST /Sale returns ID
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123", "Customer": "Test Customer"}'
        header_response.json.return_value = {
            "ID": "sale-123",
            "Customer": "Test Customer",
            "Status": "DRAFT"
        }

        # Step 2: POST /sale/order returns order with lines
        order_response = MagicMock()
        order_response.status_code = 200
        order_response.text = '{"SaleID": "sale-123", "Status": "DRAFT", "Lines": [...]}'
        order_response.json.return_value = {
            "SaleID": "sale-123",
            "Status": "DRAFT",
            "Lines": [
                {"ProductID": "prod-123", "SKU": "TEST-SKU", "Quantity": 1}
            ]
        }

        # Mock post to return different responses for each call
        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

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

        # Should have made two POST calls
        assert mock_client._request.call_count == 2

        # First call: POST /Sale (header only, no Lines)
        first_call = mock_client._request.call_args_list[0]
        assert first_call[0][0] == "post"
        assert first_call[0][1] == "Sale"
        first_payload = first_call.kwargs.get("json", first_call[1].get("json", {}))
        assert "Lines" not in first_payload
        assert first_payload.get("Customer") == "Test Customer"

        # Second call: POST /sale/order with SaleID and Lines
        second_call = mock_client._request.call_args_list[1]
        assert second_call[0][0] == "post"
        assert second_call[0][1] == "sale/order"
        second_payload = second_call.kwargs.get("json", second_call[1].get("json", {}))
        assert second_payload.get("SaleID") == "sale-123"
        assert "Lines" in second_payload
        assert len(second_payload["Lines"]) == 1

        # Result should include Order data
        assert result["ID"] == "sale-123"
        assert "Order" in result

    async def test_creates_sale_without_lines_single_step(self, mock_client):
        """Should create sale header only if no lines provided."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123", "Customer": "Test Customer"}'
        header_response.json.return_value = {
            "ID": "sale-123",
            "Customer": "Test Customer",
            "Status": "DRAFT"
        }
        mock_client._request = AsyncMock(return_value=header_response)

        payload = {
            "Customer": "Test Customer",
            "Location": "MAIN"
        }
        result = await mock_client.save_sale(payload)

        # Should only make one POST call
        assert mock_client._request.call_count == 1
        assert result["ID"] == "sale-123"

    async def test_passes_through_status_when_provided(self, mock_client):
        """Should pass Status through to the API as provided — no default injected."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123"}'
        header_response.json.return_value = {"ID": "sale-123"}
        mock_client._request = AsyncMock(return_value=header_response)

        payload = {"Customer": "Test", "Location": "MAIN", "Status": "AUTHORISED"}
        await mock_client.save_sale(payload)

        call_args = mock_client._request.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload.get("Status") == "AUTHORISED"

    async def test_passes_through_skip_quote_when_provided(self, mock_client):
        """Should pass SkipQuote through to the API as provided — no default injected."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123"}'
        header_response.json.return_value = {"ID": "sale-123"}
        mock_client._request = AsyncMock(return_value=header_response)

        payload = {"Customer": "Test", "Location": "MAIN", "SkipQuote": False}
        await mock_client.save_sale(payload)

        call_args = mock_client._request.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload.get("SkipQuote") == False

    async def test_raises_on_header_creation_error(self, mock_client):
        """Should raise Cin7ClientError if header creation fails."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Customer is required"
        mock_response.json.return_value = {"error": "Customer is required"}
        mock_client._request = AsyncMock(return_value=mock_response)

        payload = {"Location": "MAIN", "Lines": [{"ProductID": "123"}]}
        with pytest.raises(Cin7ClientError, match="header creation error"):
            await mock_client.save_sale(payload)

    async def test_raises_on_order_lines_creation_error(self, mock_client):
        """Should raise Cin7ClientError if order lines creation fails."""
        # Step 1 succeeds
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123"}'
        header_response.json.return_value = {"ID": "sale-123"}

        # Step 2 fails
        order_response = MagicMock()
        order_response.status_code = 400
        order_response.text = "Bad Request: Invalid product"
        order_response.json.return_value = {"error": "Invalid product"}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Customer": "Test",
            "Location": "MAIN",
            "Lines": [{"ProductID": "invalid"}]
        }
        with pytest.raises(Cin7ClientError, match="order lines creation error"):
            await mock_client.save_sale(payload)

    async def test_raises_if_no_sale_id_returned(self, mock_client):
        """Should raise Cin7ClientError if no ID returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"Customer": "Test"}'
        mock_response.json.return_value = {"Customer": "Test"}  # No ID field
        mock_client._request = AsyncMock(return_value=mock_response)

        payload = {"Customer": "Test", "Location": "MAIN", "Lines": [{"ProductID": "123"}]}
        with pytest.raises(Cin7ClientError, match="No ID returned"):
            await mock_client.save_sale(payload)


# ---------------------------------------------------------------------------
# TestUpdateSale (preserved from existing tests)
# ---------------------------------------------------------------------------


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
        mock_response.headers = {}
        mock_client._request = AsyncMock(return_value=mock_response)

        payload = {
            "SaleID": "abc-123",
            "Customer": "Updated Customer",
            "Location": "MAIN"
        }
        result = await mock_client.update_sale(payload)

        assert result["SaleID"] == "abc-123"
        assert result["Customer"] == "Updated Customer"
        mock_client._request.assert_called_once()

    async def test_raises_on_api_error(self, mock_client):
        """Should raise Cin7ClientError on non-2xx response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Sale not found"
        mock_response.json.return_value = {"error": "Sale not found"}
        mock_response.headers = {}
        mock_client._request = AsyncMock(return_value=mock_response)

        payload = {"SaleID": "nonexistent", "Customer": "Test"}
        with pytest.raises(Cin7ClientError, match="Sale update error"):
            await mock_client.update_sale(payload)


# ---------------------------------------------------------------------------
# TestSavePurchaseOrder (preserved from existing tests)
# ---------------------------------------------------------------------------


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
        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

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
        assert mock_client._request.call_count == 2

        # First call: POST /Purchase (header only, no Lines)
        first_call = mock_client._request.call_args_list[0]
        assert first_call[0][0] == "post"
        assert first_call[0][1] == "Purchase"
        first_payload = first_call.kwargs.get("json", first_call[1].get("json", {}))
        assert "Lines" not in first_payload
        assert first_payload.get("Supplier") == "Test Supplier"

        # Second call: POST /purchase/order with TaskID and Lines
        second_call = mock_client._request.call_args_list[1]
        assert second_call[0][0] == "post"
        assert second_call[0][1] == "purchase/order"
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
        mock_client._request = AsyncMock(return_value=header_response)

        payload = {
            "Supplier": "Test Supplier",
            "Location": "MAIN"
        }
        result = await mock_client.save_purchase_order(payload)

        # Should only make one POST call
        assert mock_client._request.call_count == 1
        assert result["ID"] == "task-123"

    async def test_passes_through_status_when_provided(self, mock_client):
        """Should pass Status through to the API as provided — no default injected."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "task-123"}'
        header_response.json.return_value = {"ID": "task-123"}
        mock_client._request = AsyncMock(return_value=header_response)

        payload = {"Supplier": "Test", "Location": "MAIN", "Status": "DRAFT"}
        await mock_client.save_purchase_order(payload)

        call_args = mock_client._request.call_args
        sent_payload = call_args.kwargs.get("json", call_args[1].get("json", {}))
        assert sent_payload.get("Status") == "DRAFT"

    async def test_raises_on_header_creation_error(self, mock_client):
        """Should raise Cin7ClientError if header creation fails."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Supplier is required"
        mock_response.json.return_value = {"error": "Supplier is required"}
        mock_client._request = AsyncMock(return_value=mock_response)

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

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

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
        mock_client._request = AsyncMock(return_value=mock_response)

        payload = {"Supplier": "Test", "Location": "MAIN", "Lines": [{"ProductID": "123"}]}
        with pytest.raises(Cin7ClientError, match="No TaskID returned"):
            await mock_client.save_purchase_order(payload)


# ---------------------------------------------------------------------------
# TestSaveSaleAdditionalChargesAndMemo
# ---------------------------------------------------------------------------


class TestSaveSaleAdditionalChargesAndMemo:
    """Tests that save_sale correctly forwards AdditionalCharges and Memo to step 2."""

    async def test_additional_charges_forwarded_to_order_step(self, mock_client):
        """AdditionalCharges and Memo should be included in the step 2 order payload."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123"}'
        header_response.json.return_value = {"ID": "sale-123"}

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.text = '{"SaleID": "sale-123", "Lines": []}'
        order_response.json.return_value = {"SaleID": "sale-123", "Lines": []}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Customer": "Test Customer",
            "Location": "MAIN",
            "Lines": [
                {"ProductID": "prod-1", "SKU": "SKU-1", "Name": "Item", "Quantity": 1,
                 "Price": 10.0, "Tax": 0, "TaxRule": "Tax Exempt", "Total": 10.0}
            ],
            "AdditionalCharges": [{"Description": "Freight", "Price": 10}],
            "Memo": "Test memo",
        }
        await mock_client.save_sale(payload)

        assert mock_client._request.call_count == 2
        second_call = mock_client._request.call_args_list[1]
        second_payload = second_call.kwargs.get("json", second_call[1].get("json", {}))
        assert second_payload["AdditionalCharges"] == [{"Description": "Freight", "Price": 10}]
        assert second_payload["Memo"] == "Test memo"

    async def test_memo_forwarded_to_order_step(self, mock_client):
        """Memo should be in step 2 payload; AdditionalCharges should NOT be present
        when it defaults to an empty list (falsy)."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123"}'
        header_response.json.return_value = {"ID": "sale-123"}

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.text = '{"SaleID": "sale-123", "Lines": []}'
        order_response.json.return_value = {"SaleID": "sale-123", "Lines": []}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Customer": "Test Customer",
            "Location": "MAIN",
            "Lines": [
                {"ProductID": "prod-1", "SKU": "SKU-1", "Name": "Item", "Quantity": 1,
                 "Price": 10.0, "Tax": 0, "TaxRule": "Tax Exempt", "Total": 10.0}
            ],
            "Memo": "Test memo only",
        }
        await mock_client.save_sale(payload)

        assert mock_client._request.call_count == 2
        second_call = mock_client._request.call_args_list[1]
        second_payload = second_call.kwargs.get("json", second_call[1].get("json", {}))
        assert second_payload["Memo"] == "Test memo only"
        assert "AdditionalCharges" not in second_payload

    async def test_payload_not_mutated(self, mock_client):
        """Original payload dict should not be mutated by save_sale."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-123"}'
        header_response.json.return_value = {"ID": "sale-123"}

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.text = '{"SaleID": "sale-123", "Lines": []}'
        order_response.json.return_value = {"SaleID": "sale-123", "Lines": []}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        original_payload = {
            "Customer": "Test Customer",
            "Location": "MAIN",
            "Lines": [{"ProductID": "prod-1", "Quantity": 1}],
            "AdditionalCharges": [{"Description": "Freight", "Price": 10}],
            "Memo": "Test memo",
        }
        await mock_client.save_sale(original_payload)

        # Original dict should still have all its keys
        assert "Lines" in original_payload
        assert "AdditionalCharges" in original_payload
        assert "Memo" in original_payload


# ---------------------------------------------------------------------------
# TestSavePurchaseOrderAdditionalChargesAndMemo
# ---------------------------------------------------------------------------


class TestSavePurchaseOrderAdditionalChargesAndMemo:
    """Tests that save_purchase_order correctly forwards AdditionalCharges and Memo."""

    async def test_additional_charges_and_memo_forwarded(self, mock_client):
        """AdditionalCharges and Memo should be included in the step 2 order payload."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "po-123"}'
        header_response.json.return_value = {"ID": "po-123"}

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.text = '{"TaskID": "po-123", "Lines": []}'
        order_response.json.return_value = {"TaskID": "po-123", "Lines": []}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Supplier": "Test Supplier",
            "Location": "MAIN",
            "Lines": [
                {"ProductID": "prod-1", "SKU": "SKU-1", "Name": "Item", "Quantity": 5,
                 "Price": 10.0, "Tax": 0, "TaxRule": "Tax Exempt", "Total": 50.0}
            ],
            "AdditionalCharges": [{"Description": "Freight", "Price": 15}],
            "Memo": "PO memo",
        }
        await mock_client.save_purchase_order(payload)

        assert mock_client._request.call_count == 2
        second_call = mock_client._request.call_args_list[1]
        second_payload = second_call.kwargs.get("json", second_call[1].get("json", {}))
        assert second_payload["AdditionalCharges"] == [{"Description": "Freight", "Price": 15}]
        assert second_payload["Memo"] == "PO memo"

    async def test_order_key_stripped_from_payload(self, mock_client):
        """Order key should be removed from step 1 payload."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "po-123"}'
        header_response.json.return_value = {"ID": "po-123"}

        mock_client._request = AsyncMock(return_value=header_response)

        payload = {
            "Supplier": "Test Supplier",
            "Location": "MAIN",
            "Order": {"Lines": [{"ProductID": "prod-1"}]},
        }
        await mock_client.save_purchase_order(payload)

        first_call = mock_client._request.call_args_list[0]
        first_payload = first_call.kwargs.get("json", first_call[1].get("json", {}))
        assert "Order" not in first_payload


# ---------------------------------------------------------------------------
# TestSaveSaleOrphanedId
# ---------------------------------------------------------------------------


class TestSaveSaleOrphanedId:
    """Tests that orphaned Sale ID appears in error messages."""

    async def test_orphaned_sale_id_in_error_message(self, mock_client):
        """When step 2 fails, the error message should contain the orphaned SaleID."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"ID": "sale-orphan-123"}'
        header_response.json.return_value = {"ID": "sale-orphan-123"}

        order_response = MagicMock()
        order_response.status_code = 400
        order_response.text = "Bad Request: Invalid product"
        order_response.json.return_value = {"error": "Invalid product"}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Customer": "Test",
            "Location": "MAIN",
            "Lines": [{"ProductID": "invalid"}],
        }
        with pytest.raises(Cin7ClientError, match=r"sale-orphan-123"):
            await mock_client.save_sale(payload)


# ---------------------------------------------------------------------------
# TestSavePurchaseOrderOrphanedId
# ---------------------------------------------------------------------------


class TestSavePurchaseOrderOrphanedId:
    """Tests that orphaned TaskID appears in error messages."""

    async def test_orphaned_task_id_in_error_message(self, mock_client):
        """When step 2 fails, the error should contain the orphaned TaskID.
        Also tests that data.get('ID') or data.get('TaskID') correctly falls back."""
        header_response = MagicMock()
        header_response.status_code = 200
        header_response.text = '{"TaskID": "po-orphan-456"}'
        header_response.json.return_value = {"TaskID": "po-orphan-456"}

        order_response = MagicMock()
        order_response.status_code = 400
        order_response.text = "Bad Request: Invalid product"
        order_response.json.return_value = {"error": "Invalid product"}

        mock_client._request = AsyncMock(side_effect=[header_response, order_response])

        payload = {
            "Supplier": "Test",
            "Location": "MAIN",
            "Lines": [{"ProductID": "invalid"}],
        }
        with pytest.raises(Cin7ClientError, match=r"po-orphan-456"):
            await mock_client.save_purchase_order(payload)


# ---------------------------------------------------------------------------
# TestNetworkErrors
# ---------------------------------------------------------------------------


class TestNetworkErrors:
    """Tests that network errors propagate and are not swallowed."""

    async def test_save_product_network_error_propagates(self, mock_client):
        """Network error in save_product should propagate, not be swallowed."""
        import httpx
        mock_client._request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.ConnectError, match="Connection refused"):
            await mock_client.save_product({"SKU": "TEST", "Name": "Test"})

    async def test_update_product_network_error_propagates(self, mock_client):
        """Network error in update_product should propagate, not be swallowed."""
        import httpx
        mock_client._request = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )

        with pytest.raises(httpx.TimeoutException, match="timeout"):
            await mock_client.update_product({"ID": "prod-123", "Name": "Test"})

    async def test_save_sale_network_error_propagates(self, mock_client):
        """Network error in save_sale should propagate, not be swallowed."""
        import httpx
        mock_client._request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.ConnectError, match="Connection refused"):
            await mock_client.save_sale({"Customer": "Test", "Location": "MAIN"})


# ---------------------------------------------------------------------------
# TestJsonParseFailures
# ---------------------------------------------------------------------------


class TestJsonParseFailures:
    """Tests for when response.json() raises on a 200 response."""

    async def test_health_check_json_parse_failure(self, mock_client):
        """health_check should still return ok with sample_count=0 when JSON parse fails."""
        response = MagicMock()
        response.status_code = 200
        response.json.side_effect = ValueError("No JSON object could be decoded")
        response.text = "<html>Server Error</html>"
        response.headers = {"X-RateLimit-Remaining": "99"}
        mock_client._request = AsyncMock(return_value=response)

        result = await mock_client.health_check()

        assert result["ok"] is True
        assert result["status"] == 200
        assert result["sample_count"] == 0

    async def test_get_product_json_parse_failure_returns_raw(self, mock_client):
        """get_product should return a dict with 'raw' key when JSON parse fails on 200."""
        response = MagicMock()
        response.status_code = 200
        response.json.side_effect = ValueError("No JSON object could be decoded")
        response.text = "<html>Server Error</html>"
        response.headers = {"X-RateLimit-Remaining": "99"}
        mock_client._request = AsyncMock(return_value=response)

        result = await mock_client.get_product(product_id="prod-123")

        assert "raw" in result

    async def test_list_products_json_parse_failure_returns_raw(self, mock_client):
        """list_products should return a dict with 'raw' key when JSON parse fails on 200."""
        response = MagicMock()
        response.status_code = 200
        response.json.side_effect = ValueError("No JSON object could be decoded")
        response.text = "<html>Server Error</html>"
        response.headers = {"X-RateLimit-Remaining": "99"}
        mock_client._request = AsyncMock(return_value=response)

        result = await mock_client.list_products()

        assert "raw" in result

    async def test_save_product_json_parse_failure_on_200(self, mock_client):
        """save_product should not crash when JSON parse fails on 200; returns dict with raw."""
        response = MagicMock()
        response.status_code = 200
        response.json.side_effect = ValueError("No JSON object could be decoded")
        response.text = "<html>Server Error</html>"
        response.headers = {"X-RateLimit-Remaining": "99"}
        mock_client._request = AsyncMock(return_value=response)

        result = await mock_client.save_product({"SKU": "TEST", "Name": "Test"})

        assert isinstance(result, dict)
        assert "raw" in result


# ---------------------------------------------------------------------------
# TestApiRequestContracts
# ---------------------------------------------------------------------------


class TestApiRequestContracts:
    """API request contract tests — verify exact HTTP method, path, and params.

    Each test documents the correct API contract per the Cin7 Core API docs:
    https://dearinventory.docs.apiary.io/

    These tests will FAIL if client methods send wrong paths or parameter names,
    forcing developers to match the API spec exactly.
    """

    def _ok_resp(self, body: dict):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = body
        resp.text = str(body)
        resp.headers = {}
        return resp

    # ---- Me ----

    async def test_get_me_path_is_lowercase_me(self, mock_client):
        """API docs: GET https://...ExternalApi/v2/me — path must be 'me' (lowercase).

        See: https://dearinventory.docs.apiary.io/#reference/me/me/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(ME_RESPONSE))

        await mock_client.get_me()

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "me", "API path is 'me' (lowercase), not 'Me'"

    # ---- Product ----

    async def test_list_products_uses_get_product_with_page_and_limit(self, mock_client):
        """API docs: GET /Product — default Page=1, Limit=100.

        See: https://dearinventory.docs.apiary.io/#reference/product/product/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(PRODUCT_LIST_RESPONSE))

        await mock_client.list_products()

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "Product"
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["Page"] == 1
        assert params["Limit"] == 100

    async def test_list_products_sku_filter_uses_sku_not_uppercase(self, mock_client):
        """API docs: GET /Product?Sku=... — param is 'Sku' (not 'SKU').

        See: https://dearinventory.docs.apiary.io/#reference/product/product/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(PRODUCT_LIST_RESPONSE))

        await mock_client.list_products(sku="TEST-001")

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert "Sku" in params, "API param is 'Sku' (not 'SKU')"
        assert "SKU" not in params

    async def test_get_product_by_sku_uses_sku_not_uppercase(self, mock_client):
        """API docs: GET /Product?Sku=... — param is 'Sku' (not 'SKU').

        See: https://dearinventory.docs.apiary.io/#reference/product/product/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp({"Products": [PRODUCT_SINGLE], "Total": 1})
        )

        await mock_client.get_product(sku="WIDGET-001")

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert "Sku" in params, "API param is 'Sku' (not 'SKU')"
        assert "SKU" not in params

    # ---- Supplier ----

    async def test_list_suppliers_uses_get_supplier_with_page_and_limit(self, mock_client):
        """API docs: GET /Supplier — default Page=1, Limit=100.

        See: https://dearinventory.docs.apiary.io/#reference/supplier/supplier/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(SUPPLIER_LIST_RESPONSE))

        await mock_client.list_suppliers()

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "Supplier"
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["Page"] == 1
        assert params["Limit"] == 100

    # ---- Sale ----

    async def test_list_sales_path_is_salelist_lowercase_l(self, mock_client):
        """API docs: GET /saleList (lowercase 'l') — not 'SaleList'.

        See: https://dearinventory.docs.apiary.io/#reference/sale/salelist/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(SALE_LIST_RESPONSE))

        await mock_client.list_sales()

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "saleList", "API path is 'saleList' (lowercase 'l'), not 'SaleList'"

    async def test_list_sales_default_page_and_limit(self, mock_client):
        """API docs: GET /saleList — default Page=1, Limit=100."""
        mock_client._request = AsyncMock(return_value=self._ok_resp(SALE_LIST_RESPONSE))

        await mock_client.list_sales()

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert params["Page"] == 1
        assert params["Limit"] == 100

    async def test_get_sale_path_is_sale_with_id(self, mock_client):
        """API docs: GET /Sale?ID=... — path is 'Sale', param is 'ID'.

        See: https://dearinventory.docs.apiary.io/#reference/sale/sale/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(SALE_SINGLE))

        await mock_client.get_sale(sale_id="sale-abc-123")

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "Sale"
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["ID"] == "sale-abc-123"

    # ---- Purchase Order ----

    async def test_list_purchase_orders_path_is_purchaselist_lowercase_l(self, mock_client):
        """API docs: GET /purchaseList (lowercase 'l') — not 'PurchaseList'.

        See: https://dearinventory.docs.apiary.io/#reference/purchase/purchaselist/get
        """
        mock_client._request = AsyncMock(return_value=self._ok_resp(PO_LIST_RESPONSE))

        await mock_client.list_purchase_orders()

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "purchaseList", (
            "API path is 'purchaseList' (lowercase 'l'), not 'PurchaseList'"
        )

    async def test_list_purchase_orders_default_page_and_limit(self, mock_client):
        """API docs: GET /purchaseList — default Page=1, Limit=100."""
        mock_client._request = AsyncMock(return_value=self._ok_resp(PO_LIST_RESPONSE))

        await mock_client.list_purchase_orders()

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert params["Page"] == 1
        assert params["Limit"] == 100

    async def test_get_purchase_order_path_is_purchase_with_id(self, mock_client):
        """API docs: GET /Purchase?ID=... — path is 'Purchase', param is 'ID'.

        See: https://dearinventory.docs.apiary.io/#reference/purchase/purchase/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp({"PurchaseList": [PO_SINGLE], "Total": 1})
        )

        await mock_client.get_purchase_order(purchase_order_id="po-abc-123")

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "Purchase"
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["ID"] == "po-abc-123"

    # ---- Stock Transfers ----

    async def test_list_stock_transfers_path_is_stocktransferlist_camelcase(self, mock_client):
        """API docs: GET /stockTransferList (camelCase) — not 'StockTransferList'.

        See: https://dearinventory.docs.apiary.io/#reference/stock/stocktransferlist/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp(STOCK_TRANSFER_LIST_RESPONSE)
        )

        await mock_client.list_stock_transfers()

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "stockTransferList", (
            "API path is 'stockTransferList' (camelCase), not 'StockTransferList'"
        )

    async def test_list_stock_transfers_default_page_and_limit(self, mock_client):
        """API docs: GET /stockTransferList — default Page=1, Limit=100."""
        mock_client._request = AsyncMock(
            return_value=self._ok_resp(STOCK_TRANSFER_LIST_RESPONSE)
        )

        await mock_client.list_stock_transfers()

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert params["Page"] == 1
        assert params["Limit"] == 100

    async def test_get_stock_transfer_path_is_stocktransfer_camelcase(self, mock_client):
        """API docs: GET /stockTransfer?TaskID=... — path is 'stockTransfer' (camelCase).

        See: https://dearinventory.docs.apiary.io/#reference/stock/stocktransfer/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp(
                {"StockTransferList": [STOCK_TRANSFER_SINGLE], "Total": 1}
            )
        )

        await mock_client.get_stock_transfer(stock_transfer_id="st-task-001")

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "stockTransfer", (
            "API path is 'stockTransfer' (camelCase), not 'StockTransfer'"
        )
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params["TaskID"] == "st-task-001"

    # ---- Product Availability ----

    async def test_list_product_availability_uses_id_and_sku_params(self, mock_client):
        """API docs: GET /ref/productavailability uses 'ID' and 'Sku' params.

        API params: ID (Guid), Name, Sku, Location, Batch, Category
        See: https://dearinventory.docs.apiary.io/#reference/product/product-availability/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp({"ProductAvailabilityList": [], "Total": 0})
        )

        await mock_client.list_product_availability(
            product_id="prod-abc-123", sku="WIDGET-001"
        )

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "ref/productavailability"
        params = call.kwargs.get("params", call[1].get("params", {}))
        assert params.get("ID") == "prod-abc-123", "API param is 'ID' not 'ProductID'"
        assert "ProductID" not in params, "Must not send 'ProductID' — API param is 'ID'"
        assert params.get("Sku") == "WIDGET-001", "API param is 'Sku' not 'SKU'"
        assert "SKU" not in params, "Must not send 'SKU' — API param is 'Sku'"

    async def test_list_product_availability_default_page_and_limit(self, mock_client):
        """API docs: GET /ref/productavailability — default Page=1, Limit=100."""
        mock_client._request = AsyncMock(
            return_value=self._ok_resp({"ProductAvailabilityList": [], "Total": 0})
        )

        await mock_client.list_product_availability()

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert params["Page"] == 1
        assert params["Limit"] == 100

    # ---- Product Suppliers ----

    async def test_get_product_suppliers_path_is_product_suppliers_kebab(self, mock_client):
        """API docs: GET /product-suppliers — path is 'product-suppliers' (lowercase, hyphenated).

        See: https://dearinventory.docs.apiary.io/#reference/reference-books/product-suppliers/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp(PRODUCT_SUPPLIERS_RESPONSE)
        )

        await mock_client.get_product_suppliers(product_id="prod-abc-123")

        call = mock_client._request.call_args
        assert call[0][0] == "get"
        assert call[0][1] == "product-suppliers", (
            "API path is 'product-suppliers' (kebab-case), not 'ProductSuppliers'"
        )

    async def test_get_product_suppliers_param_is_productid_guid(self, mock_client):
        """API docs: GET /product-suppliers?ProductID=... — param is 'ProductID' (Guid).

        See: https://dearinventory.docs.apiary.io/#reference/reference-books/product-suppliers/get
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp(PRODUCT_SUPPLIERS_RESPONSE)
        )

        await mock_client.get_product_suppliers(product_id="prod-abc-123")

        params = mock_client._request.call_args.kwargs.get("params", {})
        assert params.get("ProductID") == "prod-abc-123", "API param is 'ProductID' not 'ID'"
        assert "ID" not in params, "Must not send 'ID' — API param is 'ProductID'"

    async def test_update_product_suppliers_path_is_product_suppliers_kebab(self, mock_client):
        """API docs: PUT /product-suppliers — path is 'product-suppliers' (kebab-case).

        See: https://dearinventory.docs.apiary.io/#reference/reference-books/product-suppliers/put
        """
        mock_client._request = AsyncMock(
            return_value=self._ok_resp(PRODUCT_SUPPLIERS_UPDATE_RESPONSE)
        )

        await mock_client.update_product_suppliers([{"ProductID": "prod-abc-123"}])

        call = mock_client._request.call_args
        assert call[0][0] == "put"
        assert call[0][1] == "product-suppliers", (
            "API path is 'product-suppliers' (kebab-case), not 'ProductSuppliers'"
        )
