"""Tests for MCP server tools."""

import copy
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.fixtures.common import HEALTH_CHECK_RESPONSE, ME_RESPONSE
from tests.fixtures.products import (
    PRODUCT_LIST_RESPONSE,
    PRODUCT_SINGLE,
    PRODUCT_SAVE_RESPONSE,
    PRODUCT_UPDATE_RESPONSE,
    PRODUCT_SUPPLIERS_UPDATE_RESPONSE,
)
from tests.fixtures.suppliers import (
    SUPPLIER_LIST_RESPONSE,
    SUPPLIER_SINGLE,
    SUPPLIER_SAVE_RESPONSE,
    SUPPLIER_UPDATE_RESPONSE,
)
from tests.fixtures.sales import (
    SALE_LIST_RESPONSE,
    SALE_SINGLE,
)
from tests.fixtures.purchase_orders import (
    PO_LIST_RESPONSE,
    PO_SINGLE,
    PO_ORDER_RESPONSE,
)
from tests.fixtures.stock_transfers import (
    STOCK_TRANSFER_LIST_RESPONSE,
    STOCK_TRANSFER_SINGLE,
)


# ---------------------------------------------------------------------------
# TestCin7Status
# ---------------------------------------------------------------------------


class TestCin7Status:
    """Tests for cin7_status tool."""

    @pytest.mark.asyncio
    async def test_success_returns_health_check(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.health_check = AsyncMock(return_value=HEALTH_CHECK_RESPONSE)

        from cin7_core_server.resources.auth import cin7_status

        result = await cin7_status()

        mock_instance.health_check.assert_called_once()
        assert result == HEALTH_CHECK_RESPONSE


# ---------------------------------------------------------------------------
# TestCin7Me
# ---------------------------------------------------------------------------


class TestCin7Me:
    """Tests for cin7_me tool."""

    @pytest.mark.asyncio
    async def test_success_returns_me(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_me = AsyncMock(return_value=ME_RESPONSE)

        from cin7_core_server.resources.auth import cin7_me

        result = await cin7_me()

        mock_instance.get_me.assert_called_once()
        assert result == ME_RESPONSE


# ---------------------------------------------------------------------------
# TestCin7Products
# ---------------------------------------------------------------------------


class TestCin7Products:
    """Tests for cin7_products tool."""

    @pytest.mark.asyncio
    async def test_calls_list_products_with_correct_args(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_products = AsyncMock(return_value=copy.deepcopy(PRODUCT_LIST_RESPONSE))

        from cin7_core_server.resources.products import cin7_products

        result = await cin7_products(page=2, limit=50, name="Widget", sku="W-001")

        mock_instance.list_products.assert_called_once_with(
            page=2, limit=50, name="Widget", sku="W-001"
        )


    @pytest.mark.asyncio
    async def test_default_projection_keeps_sku_and_name(self, mock_cin7_class):
        """Default projection should only keep SKU and Name from Products list."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_products = AsyncMock(return_value=copy.deepcopy(PRODUCT_LIST_RESPONSE))

        from cin7_core_server.resources.products import cin7_products

        result = await cin7_products()

        products = result["Products"]
        for product in products:
            assert "SKU" in product
            assert "Name" in product
            # Extra fields should be stripped
            assert "ID" not in product
            assert "Category" not in product
            assert "Brand" not in product
            assert "PriceTier1" not in product

    @pytest.mark.asyncio
    async def test_extra_fields_preserved_in_projection(self, mock_cin7_class):
        """Requested extra fields should be preserved alongside SKU and Name."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_products = AsyncMock(return_value=copy.deepcopy(PRODUCT_LIST_RESPONSE))

        from cin7_core_server.resources.products import cin7_products

        result = await cin7_products(fields=["PriceTier1", "Category"])

        products = result["Products"]
        for product in products:
            assert "SKU" in product
            assert "Name" in product
            assert "PriceTier1" in product
            assert "Category" in product
            # Non-requested fields still excluded
            assert "ID" not in product
            assert "Brand" not in product


# ---------------------------------------------------------------------------
# TestCin7GetProduct
# ---------------------------------------------------------------------------


class TestCin7GetProduct:
    """Tests for cin7_get_product tool."""

    @pytest.mark.asyncio
    async def test_by_id(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from cin7_core_server.resources.products import cin7_get_product

        result = await cin7_get_product(product_id="prod-abc-123")

        mock_instance.get_product.assert_called_once_with(
            product_id="prod-abc-123", sku=None
        )
        assert result == PRODUCT_SINGLE

    @pytest.mark.asyncio
    async def test_by_sku(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from cin7_core_server.resources.products import cin7_get_product

        result = await cin7_get_product(sku="WIDGET-001")

        mock_instance.get_product.assert_called_once_with(
            product_id=None, sku="WIDGET-001"
        )
        assert result == PRODUCT_SINGLE


# ---------------------------------------------------------------------------
# TestCin7CreateProduct
# ---------------------------------------------------------------------------


class TestCin7CreateProduct:
    """Tests for cin7_create_product tool."""

    @pytest.mark.asyncio
    async def test_basic_no_suppliers(self, mock_cin7_class):
        """Product without Suppliers array calls save_product only."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_product = AsyncMock(return_value=PRODUCT_SAVE_RESPONSE)

        from cin7_core_server.resources.products import cin7_create_product

        payload = {"SKU": "NEWPROD-001", "Name": "New Product", "Category": "Test"}
        result = await cin7_create_product(payload)

        mock_instance.save_product.assert_called_once_with(payload)
        assert result["ID"] == "prod-new-789"


    @pytest.mark.asyncio
    async def test_with_suppliers(self, mock_cin7_class):
        """Product with Suppliers calls save_product then update_product_suppliers."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_product = AsyncMock(return_value=PRODUCT_SAVE_RESPONSE)
        mock_instance.update_product_suppliers = AsyncMock(
            return_value=PRODUCT_SUPPLIERS_UPDATE_RESPONSE
        )

        from cin7_core_server.resources.products import cin7_create_product

        suppliers = [{"SupplierID": "sup-222", "SupplierName": "New Supplier", "Cost": 10.00}]
        payload = {
            "SKU": "NEWPROD-001",
            "Name": "New Product",
            "Category": "Test",
            "Suppliers": suppliers,
        }
        result = await cin7_create_product(payload)

        # save_product should receive payload WITHOUT Suppliers
        mock_instance.save_product.assert_called_once_with(
            {"SKU": "NEWPROD-001", "Name": "New Product", "Category": "Test"}
        )
        # update_product_suppliers should be called with product ID from response
        mock_instance.update_product_suppliers.assert_called_once_with(
            [{"ProductID": "prod-new-789", "Suppliers": suppliers}]
        )
        assert result["_suppliersRegistered"] is True
        assert result["_supplierCount"] == 1

    @pytest.mark.asyncio
    async def test_supplier_registration_failure(self, mock_cin7_class):
        """If supplier registration fails, product is still created but error captured."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_product = AsyncMock(return_value=PRODUCT_SAVE_RESPONSE)
        mock_instance.update_product_suppliers = AsyncMock(
            side_effect=Exception("Supplier API error")
        )

        from cin7_core_server.resources.products import cin7_create_product

        suppliers = [{"SupplierID": "sup-bad", "SupplierName": "Bad Supplier"}]
        payload = {
            "SKU": "NEWPROD-001",
            "Name": "New Product",
            "Category": "Test",
            "Suppliers": suppliers,
        }
        result = await cin7_create_product(payload)

        # Product should still be created
        assert result["ID"] == "prod-new-789"
        assert result["_suppliersRegistered"] is False
        assert "Supplier API error" in result["_supplierError"]




# ---------------------------------------------------------------------------
# TestCin7UpdateProduct
# ---------------------------------------------------------------------------


class TestCin7UpdateProduct:
    """Tests for cin7_update_product tool."""

    @pytest.mark.asyncio
    async def test_basic_no_suppliers(self, mock_cin7_class):
        """Update without Suppliers calls update_product only."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.update_product = AsyncMock(return_value=PRODUCT_UPDATE_RESPONSE)

        from cin7_core_server.resources.products import cin7_update_product

        payload = {"ID": "prod-abc-123", "Name": "Updated Widget"}
        result = await cin7_update_product(payload)

        mock_instance.update_product.assert_called_once_with(payload)
        assert result["Name"] == "Updated Widget"


    @pytest.mark.asyncio
    async def test_with_suppliers_extracts_product_id_from_payload(self, mock_cin7_class):
        """Update with Suppliers calls update_product then update_product_suppliers,
        extracting product ID from the payload."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.update_product = AsyncMock(return_value=PRODUCT_UPDATE_RESPONSE)
        mock_instance.update_product_suppliers = AsyncMock(
            return_value=PRODUCT_SUPPLIERS_UPDATE_RESPONSE
        )

        from cin7_core_server.resources.products import cin7_update_product

        suppliers = [{"SupplierID": "sup-222", "SupplierName": "New Supplier", "Cost": 10.00}]
        payload = {
            "ID": "prod-abc-123",
            "Name": "Updated Widget",
            "Suppliers": suppliers,
        }
        result = await cin7_update_product(payload)

        # update_product should receive payload WITHOUT Suppliers
        mock_instance.update_product.assert_called_once_with(
            {"ID": "prod-abc-123", "Name": "Updated Widget"}
        )
        # update_product_suppliers uses the ID from the payload
        mock_instance.update_product_suppliers.assert_called_once_with(
            [{"ProductID": "prod-abc-123", "Suppliers": suppliers}]
        )
        assert result["_suppliersUpdated"] is True
        assert result["_supplierCount"] == 1

    @pytest.mark.asyncio
    async def test_supplier_update_failure(self, mock_cin7_class):
        """If supplier update fails, product is still updated but error captured."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.update_product = AsyncMock(return_value=PRODUCT_UPDATE_RESPONSE)
        mock_instance.update_product_suppliers = AsyncMock(
            side_effect=Exception("Supplier update failed")
        )

        from cin7_core_server.resources.products import cin7_update_product

        suppliers = [{"SupplierID": "sup-bad"}]
        payload = {
            "ID": "prod-abc-123",
            "Name": "Updated Widget",
            "Suppliers": suppliers,
        }
        result = await cin7_update_product(payload)

        assert result["ID"] == "prod-abc-123"
        assert result["_suppliersUpdated"] is False
        assert "Supplier update failed" in result["_supplierError"]




# ---------------------------------------------------------------------------
# TestCin7Suppliers
# ---------------------------------------------------------------------------


class TestCin7Suppliers:
    """Tests for cin7_suppliers tool."""

    @pytest.mark.asyncio
    async def test_calls_list_suppliers_with_correct_args(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_suppliers = AsyncMock(return_value=SUPPLIER_LIST_RESPONSE)

        from cin7_core_server.resources.suppliers import cin7_suppliers

        result = await cin7_suppliers(page=1, limit=50)

        mock_instance.list_suppliers.assert_called_once_with(page=1, limit=50, name=None)
        assert result == SUPPLIER_LIST_RESPONSE


    @pytest.mark.asyncio
    async def test_with_name_filter(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_suppliers = AsyncMock(return_value=SUPPLIER_LIST_RESPONSE)

        from cin7_core_server.resources.suppliers import cin7_suppliers

        result = await cin7_suppliers(name="Acme")

        mock_instance.list_suppliers.assert_called_once_with(page=1, limit=100, name="Acme")



# ---------------------------------------------------------------------------
# TestCin7GetSupplier
# ---------------------------------------------------------------------------


class TestCin7GetSupplier:
    """Tests for cin7_get_supplier tool."""

    @pytest.mark.asyncio
    async def test_by_id(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from cin7_core_server.resources.suppliers import cin7_get_supplier

        result = await cin7_get_supplier(supplier_id="sup-abc-123")

        mock_instance.get_supplier.assert_called_once_with(
            supplier_id="sup-abc-123", name=None
        )
        assert result == SUPPLIER_SINGLE

    @pytest.mark.asyncio
    async def test_by_name(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from cin7_core_server.resources.suppliers import cin7_get_supplier

        result = await cin7_get_supplier(name="Acme Supplies")

        mock_instance.get_supplier.assert_called_once_with(
            supplier_id=None, name="Acme Supplies"
        )
        assert result == SUPPLIER_SINGLE




# ---------------------------------------------------------------------------
# TestCin7CreateSupplier
# ---------------------------------------------------------------------------


class TestCin7CreateSupplier:
    """Tests for cin7_create_supplier tool."""

    @pytest.mark.asyncio
    async def test_calls_save_supplier(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_supplier = AsyncMock(return_value=SUPPLIER_SAVE_RESPONSE)

        from cin7_core_server.resources.suppliers import cin7_create_supplier

        payload = {"Name": "New Supplier", "ContactPerson": "Bob Wilson"}
        result = await cin7_create_supplier(payload)

        mock_instance.save_supplier.assert_called_once_with(payload)
        assert result["ID"] == "sup-new-789"
        assert result["Name"] == "New Supplier"




# ---------------------------------------------------------------------------
# TestCin7UpdateSupplier
# ---------------------------------------------------------------------------


class TestCin7UpdateSupplier:
    """Tests for cin7_update_supplier tool."""

    @pytest.mark.asyncio
    async def test_calls_update_supplier(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.update_supplier = AsyncMock(return_value=SUPPLIER_UPDATE_RESPONSE)

        from cin7_core_server.resources.suppliers import cin7_update_supplier

        payload = {"ID": "sup-abc-123", "Name": "Acme Supplies Updated"}
        result = await cin7_update_supplier(payload)

        mock_instance.update_supplier.assert_called_once_with(payload)
        assert result["Name"] == "Acme Supplies Updated"




# ---------------------------------------------------------------------------
# TestCin7Sales
# ---------------------------------------------------------------------------


class TestCin7Sales:
    """Tests for cin7_sales tool."""

    @pytest.mark.asyncio
    async def test_calls_list_sales(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_sales = AsyncMock(return_value=copy.deepcopy(SALE_LIST_RESPONSE))

        from cin7_core_server.resources.sales import cin7_sales

        result = await cin7_sales(page=1, limit=50, search="test")

        mock_instance.list_sales.assert_called_once_with(page=1, limit=50, search="test")


    @pytest.mark.asyncio
    async def test_default_projection_keeps_base_fields(self, mock_cin7_class):
        """Default projection keeps Order, SaleOrderNumber, Customer, Location."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_sales = AsyncMock(return_value=copy.deepcopy(SALE_LIST_RESPONSE))

        from cin7_core_server.resources.sales import cin7_sales

        result = await cin7_sales()

        sales = result["SaleList"]
        for sale in sales:
            assert "Order" in sale
            assert "SaleOrderNumber" in sale
            assert "Customer" in sale
            assert "Location" in sale
            # Extra fields should be stripped
            assert "Status" not in sale
            assert "Total" not in sale
            assert "OrderDate" not in sale

    @pytest.mark.asyncio
    async def test_extra_fields_preserved(self, mock_cin7_class):
        """Requested extra fields should be preserved alongside base fields."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_sales = AsyncMock(return_value=copy.deepcopy(SALE_LIST_RESPONSE))

        from cin7_core_server.resources.sales import cin7_sales

        result = await cin7_sales(fields=["Status", "Total"])

        sales = result["SaleList"]
        for sale in sales:
            assert "Order" in sale
            assert "SaleOrderNumber" in sale
            assert "Customer" in sale
            assert "Location" in sale
            assert "Status" in sale
            assert "Total" in sale
            # Still excluded
            assert "OrderDate" not in sale




# ---------------------------------------------------------------------------
# TestCin7GetSale
# ---------------------------------------------------------------------------


class TestCin7GetSale:
    """Tests for cin7_get_sale tool."""

    @pytest.mark.asyncio
    async def test_calls_get_sale(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_sale = AsyncMock(return_value=SALE_SINGLE)

        from cin7_core_server.resources.sales import cin7_get_sale

        result = await cin7_get_sale(sale_id="sale-abc-123")

        mock_instance.get_sale.assert_called_once_with(
            sale_id="sale-abc-123",
            combine_additional_charges=False,
            hide_inventory_movements=False,
            include_transactions=False,
        )
        assert result == SALE_SINGLE


    @pytest.mark.asyncio
    async def test_passes_optional_params(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_sale = AsyncMock(return_value=SALE_SINGLE)

        from cin7_core_server.resources.sales import cin7_get_sale

        result = await cin7_get_sale(
            sale_id="sale-abc-123",
            combine_additional_charges=True,
            hide_inventory_movements=True,
            include_transactions=True,
        )

        mock_instance.get_sale.assert_called_once_with(
            sale_id="sale-abc-123",
            combine_additional_charges=True,
            hide_inventory_movements=True,
            include_transactions=True,
        )



# ---------------------------------------------------------------------------
# TestCin7PurchaseOrders
# ---------------------------------------------------------------------------


class TestCin7PurchaseOrders:
    """Tests for cin7_purchase_orders tool."""

    @pytest.mark.asyncio
    async def test_calls_list_purchase_orders(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_purchase_orders = AsyncMock(return_value=copy.deepcopy(PO_LIST_RESPONSE))

        from cin7_core_server.resources.purchase_orders import cin7_purchase_orders

        result = await cin7_purchase_orders(page=1, limit=50, search="acme")

        mock_instance.list_purchase_orders.assert_called_once_with(
            page=1, limit=50, search="acme"
        )


    @pytest.mark.asyncio
    async def test_default_projection_keeps_base_fields(self, mock_cin7_class):
        """Default projection keeps TaskID, Supplier, Status, OrderDate, Location."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_purchase_orders = AsyncMock(return_value=copy.deepcopy(PO_LIST_RESPONSE))

        from cin7_core_server.resources.purchase_orders import cin7_purchase_orders

        result = await cin7_purchase_orders()

        purchases = result["PurchaseList"]
        for po in purchases:
            assert "TaskID" in po
            assert "Supplier" in po
            assert "Status" in po
            assert "OrderDate" in po
            assert "Location" in po
            # Extra fields should be stripped
            assert "Total" not in po
            assert "RequiredBy" not in po

    @pytest.mark.asyncio
    async def test_extra_fields_preserved(self, mock_cin7_class):
        """Requested extra fields should be preserved alongside base fields."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_purchase_orders = AsyncMock(return_value=copy.deepcopy(PO_LIST_RESPONSE))

        from cin7_core_server.resources.purchase_orders import cin7_purchase_orders

        result = await cin7_purchase_orders(fields=["Total", "RequiredBy"])

        purchases = result["PurchaseList"]
        for po in purchases:
            assert "TaskID" in po
            assert "Supplier" in po
            assert "Status" in po
            assert "OrderDate" in po
            assert "Location" in po
            assert "Total" in po
            assert "RequiredBy" in po




# ---------------------------------------------------------------------------
# TestCin7GetPurchaseOrder
# ---------------------------------------------------------------------------


class TestCin7GetPurchaseOrder:
    """Tests for cin7_get_purchase_order tool."""

    @pytest.mark.asyncio
    async def test_calls_get_purchase_order(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_purchase_order = AsyncMock(return_value=PO_SINGLE)

        from cin7_core_server.resources.purchase_orders import cin7_get_purchase_order

        result = await cin7_get_purchase_order(purchase_order_id="po-task-001")

        mock_instance.get_purchase_order.assert_called_once_with(
            purchase_order_id="po-task-001"
        )
        assert result == PO_SINGLE




# ---------------------------------------------------------------------------
# TestCin7CreatePurchaseOrder
# ---------------------------------------------------------------------------


class TestCin7CreatePurchaseOrder:
    """Tests for cin7_create_purchase_order tool."""

    @pytest.mark.asyncio
    async def test_calls_save_purchase_order(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_purchase_order = AsyncMock(return_value=PO_ORDER_RESPONSE)

        from cin7_core_server.resources.purchase_orders import cin7_create_purchase_order

        payload = {
            "Supplier": "Acme Supplies",
            "Location": "Main Warehouse",
            "OrderDate": "2024-06-01",
            "Lines": [
                {
                    "ProductID": "prod-abc-123",
                    "SKU": "WIDGET-001",
                    "Name": "Blue Widget",
                    "Quantity": 5,
                    "Price": 12.50,
                    "Tax": 0,
                    "TaxRule": "Tax Exempt",
                    "Total": 62.50,
                }
            ],
        }
        result = await cin7_create_purchase_order(payload)

        mock_instance.save_purchase_order.assert_called_once_with(payload)
        assert result["TaskID"] == "po-new-789"





# ---------------------------------------------------------------------------
# TestCin7StockTransfers
# ---------------------------------------------------------------------------


class TestCin7StockTransfers:
    """Tests for cin7_stock_transfers tool."""

    @pytest.mark.asyncio
    async def test_calls_list_stock_transfers(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_stock_transfers = AsyncMock(
            return_value=copy.deepcopy(STOCK_TRANSFER_LIST_RESPONSE)
        )

        from cin7_core_server.resources.stock import cin7_stock_transfers

        result = await cin7_stock_transfers(page=1, limit=50, search="restock")

        mock_instance.list_stock_transfers.assert_called_once_with(
            page=1, limit=50, search="restock"
        )


    @pytest.mark.asyncio
    async def test_default_projection_keeps_base_fields(self, mock_cin7_class):
        """Default projection keeps TaskID, FromLocation, ToLocation, Status, TransferDate."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_stock_transfers = AsyncMock(
            return_value=copy.deepcopy(STOCK_TRANSFER_LIST_RESPONSE)
        )

        from cin7_core_server.resources.stock import cin7_stock_transfers

        result = await cin7_stock_transfers()

        transfers = result["StockTransferList"]
        for transfer in transfers:
            assert "TaskID" in transfer
            assert "FromLocation" in transfer
            assert "ToLocation" in transfer
            assert "Status" in transfer
            assert "TransferDate" in transfer
            # Extra fields should be stripped
            assert "Note" not in transfer

    @pytest.mark.asyncio
    async def test_extra_fields_preserved(self, mock_cin7_class):
        """Requested extra fields should be preserved alongside base fields."""
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_stock_transfers = AsyncMock(
            return_value=copy.deepcopy(STOCK_TRANSFER_LIST_RESPONSE)
        )

        from cin7_core_server.resources.stock import cin7_stock_transfers

        result = await cin7_stock_transfers(fields=["Note"])

        transfers = result["StockTransferList"]
        for transfer in transfers:
            assert "TaskID" in transfer
            assert "FromLocation" in transfer
            assert "ToLocation" in transfer
            assert "Status" in transfer
            assert "TransferDate" in transfer
            assert "Note" in transfer





# ---------------------------------------------------------------------------
# TestCin7GetStockTransfer
# ---------------------------------------------------------------------------


class TestCin7GetStockTransfer:
    """Tests for cin7_get_stock_transfer tool."""

    @pytest.mark.asyncio
    async def test_calls_get_stock_transfer(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_stock_transfer = AsyncMock(return_value=STOCK_TRANSFER_SINGLE)

        from cin7_core_server.resources.stock import cin7_get_stock_transfer

        result = await cin7_get_stock_transfer(stock_transfer_id="st-task-001")

        mock_instance.get_stock_transfer.assert_called_once_with(
            stock_transfer_id="st-task-001"
        )
        assert result == STOCK_TRANSFER_SINGLE





# ---------------------------------------------------------------------------
# TestStockLevelsTools (KEPT AS-IS)
# ---------------------------------------------------------------------------


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

        with patch("cin7_core_server.resources.stock.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value=mock_result)
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.stock import cin7_stock_levels

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

        with patch("cin7_core_server.resources.stock.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value=mock_result)
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.stock import cin7_stock_levels

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

        with patch("cin7_core_server.resources.stock.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.get_product_availability = AsyncMock(return_value=mock_result)
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.stock import cin7_get_stock

            result = await cin7_get_stock(sku="TEST-001")

            assert result["sku"] == "TEST-001"
            assert len(result["locations"]) == 2
            assert result["total_on_hand"] == 60.0
            assert result["total_available"] == 55.0


# ---------------------------------------------------------------------------
# TestStockSnapshotTools (KEPT AS-IS)
# ---------------------------------------------------------------------------


class TestStockSnapshotTools:
    """Tests for stock snapshot tools."""

    @pytest.mark.asyncio
    async def test_snapshot_start_returns_id(self):
        """Should return a snapshot ID when started."""
        with patch("cin7_core_server.resources.snapshots.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [],
                "Total": 0,
            })
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.snapshots import cin7_stock_snapshot_start

            result = await cin7_stock_snapshot_start()

            assert "snapshotId" in result
            assert isinstance(result["snapshotId"], str)
            assert len(result["snapshotId"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_snapshot_status_returns_progress(self):
        """Should return snapshot status."""
        with patch("cin7_core_server.resources.snapshots.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [{"SKU": "A", "Location": "M", "OnHand": 1, "Available": 1}],
                "Total": 1,
            })
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.snapshots import (
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
        with patch("cin7_core_server.resources.snapshots.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [
                    {"SKU": "A", "Location": "M", "OnHand": 1, "Available": 1},
                    {"SKU": "B", "Location": "M", "OnHand": 2, "Available": 2},
                ],
                "Total": 2,
            })
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.snapshots import (
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
        with patch("cin7_core_server.resources.snapshots.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.list_product_availability = AsyncMock(return_value={
                "ProductAvailabilityList": [],
                "Total": 0,
            })
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.snapshots import (
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


# ---------------------------------------------------------------------------
# TestSaleTools (KEPT AS-IS)
# ---------------------------------------------------------------------------


class TestSaleTools:
    """Tests for sale creation and update tools."""

    @pytest.mark.asyncio
    async def test_cin7_create_sale_calls_client(self):
        """Should call save_sale on client and return result."""
        mock_result = {
            "SaleID": "sale-123",
            "Customer": "Test Customer",
            "Status": "DRAFT",
            "Quote": {"Status": "DRAFT", "Lines": []}
        }

        with patch("cin7_core_server.resources.sales.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.save_sale = AsyncMock(return_value=mock_result)
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.sales import cin7_create_sale

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
            result = await cin7_create_sale(payload)

            assert result["SaleID"] == "sale-123"
            assert result["Customer"] == "Test Customer"
            mock_client.save_sale.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_cin7_update_sale_calls_client(self):
        """Should call update_sale on client and return result."""
        mock_result = {
            "SaleID": "sale-123",
            "Customer": "Updated Customer",
            "Status": "DRAFT"
        }

        with patch("cin7_core_server.resources.sales.Cin7Client") as mock_class:
            mock_client = MagicMock()
            mock_client.update_sale = AsyncMock(return_value=mock_result)
            mock_class.from_env.return_value = mock_client

            from cin7_core_server.resources.sales import cin7_update_sale

            payload = {
                "SaleID": "sale-123",
                "Customer": "Updated Customer"
            }
            result = await cin7_update_sale(payload)

            assert result["SaleID"] == "sale-123"
            assert result["Customer"] == "Updated Customer"
            mock_client.update_sale.assert_called_once_with(payload)


# ---------------------------------------------------------------------------
# TestCin7GetStockEdgeCases
# ---------------------------------------------------------------------------


class TestCin7GetStockEdgeCases:
    """Tests for edge cases in cin7_get_stock tool."""

    @pytest.mark.asyncio
    async def test_empty_locations_returns_zeros(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product_availability = AsyncMock(return_value=[])

        from cin7_core_server.resources.stock import cin7_get_stock

        result = await cin7_get_stock(sku="MISSING")

        assert result["total_on_hand"] == 0
        assert result["total_available"] == 0
        assert result["locations"] == []
        assert result["sku"] == "MISSING"
        assert result["product_id"] is None

    @pytest.mark.asyncio
    async def test_none_values_in_location_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product_availability = AsyncMock(return_value=[
            {"SKU": "X", "OnHand": None, "Available": None, "ProductID": "p1"}
        ])

        from cin7_core_server.resources.stock import cin7_get_stock

        result = await cin7_get_stock(sku="X")

        assert result["total_on_hand"] == 0
        assert result["total_available"] == 0


# ---------------------------------------------------------------------------
# TestProductsProjectionEdgeCases
# ---------------------------------------------------------------------------


class TestProductsProjectionEdgeCases:
    """Tests for edge cases in cin7_products field projection."""

    @pytest.mark.asyncio
    async def test_empty_fields_list_same_as_none(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_products = AsyncMock(return_value=copy.deepcopy(PRODUCT_LIST_RESPONSE))

        from cin7_core_server.resources.products import cin7_products

        result = await cin7_products(fields=[])

        products = result["Products"]
        for product in products:
            assert "SKU" in product
            assert "Name" in product
            # Extra fields should be stripped (same as default)
            assert "ID" not in product
            assert "Category" not in product
            assert "Brand" not in product
            assert "PriceTier1" not in product

    @pytest.mark.asyncio
    async def test_nonexistent_field_silently_absent(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.list_products = AsyncMock(return_value=copy.deepcopy(PRODUCT_LIST_RESPONSE))

        from cin7_core_server.resources.products import cin7_products

        result = await cin7_products(fields=["NonExistentField"])

        products = result["Products"]
        for product in products:
            assert "SKU" in product
            assert "Name" in product
            assert "NonExistentField" not in product


# ---------------------------------------------------------------------------
# TestCreateProductSupplierEdgeCases
# ---------------------------------------------------------------------------


class TestCreateProductSupplierEdgeCases:
    """Tests for edge cases in cin7_create_product supplier handling."""

    @pytest.mark.asyncio
    async def test_empty_suppliers_list_skips_registration(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_product = AsyncMock(return_value=copy.deepcopy(PRODUCT_SAVE_RESPONSE))

        from cin7_core_server.resources.products import cin7_create_product

        payload = {
            "SKU": "NEWPROD-001",
            "Name": "New Product",
            "Category": "Test",
            "Suppliers": [],
        }
        result = await cin7_create_product(payload)

        mock_instance.save_product.assert_called_once()
        mock_instance.update_product_suppliers.assert_not_called()
        assert result["ID"] == "prod-new-789"

    @pytest.mark.asyncio
    async def test_no_product_id_in_response_with_suppliers(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.save_product = AsyncMock(return_value={"Name": "Test"})

        from cin7_core_server.resources.products import cin7_create_product

        payload = {
            "SKU": "NEWPROD-001",
            "Name": "New Product",
            "Category": "Test",
            "Suppliers": [{"SupplierID": "s1"}],
        }
        result = await cin7_create_product(payload)

        mock_instance.update_product_suppliers.assert_not_called()
        assert result["_suppliersRegistered"] is False
