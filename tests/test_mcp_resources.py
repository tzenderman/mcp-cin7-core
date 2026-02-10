"""Tests for MCP server resource handler functions."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock

from tests.fixtures.products import PRODUCT_SINGLE
from tests.fixtures.suppliers import SUPPLIER_SINGLE
from tests.fixtures.purchase_orders import PO_SINGLE
from tests.fixtures.sales import SALE_SINGLE


# ----------------------------- Product Template -----------------------------


class TestProductTemplate:
    """Tests for resource_product_template()."""

    @pytest.mark.asyncio
    async def test_returns_valid_json_with_required_fields(self):
        from mcp_cin7_core.mcp_server import resource_product_template

        result = await resource_product_template()
        template = json.loads(result)

        for field in ("SKU", "Name", "Category", "Status", "Type", "UOM",
                      "CostingMethod", "DefaultLocation"):
            assert field in template, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_has_correct_defaults(self):
        from mcp_cin7_core.mcp_server import resource_product_template

        result = await resource_product_template()
        template = json.loads(result)

        assert template["Status"] == "Active"
        assert template["Type"] == "Stock"
        assert template["UOM"] == "Item"
        assert template["CostingMethod"] == "FIFO"

    @pytest.mark.asyncio
    async def test_includes_suppliers_array(self):
        from mcp_cin7_core.mcp_server import resource_product_template

        result = await resource_product_template()
        template = json.loads(result)

        assert "Suppliers" in template
        assert isinstance(template["Suppliers"], list)


# ----------------------------- Product By ID -----------------------------


class TestProductById:
    """Tests for resource_product_by_id()."""

    @pytest.mark.asyncio
    async def test_calls_get_product_with_product_id(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from mcp_cin7_core.mcp_server import resource_product_by_id

        result = await resource_product_by_id("prod-abc-123")

        assert isinstance(result, str)
        mock_instance.get_product.assert_called_once_with(product_id="prod-abc-123")

    @pytest.mark.asyncio
    async def test_returned_json_matches_mock_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from mcp_cin7_core.mcp_server import resource_product_by_id

        result = await resource_product_by_id("prod-abc-123")
        data = json.loads(result)

        assert data["SKU"] == "WIDGET-001"
        assert data["Name"] == "Blue Widget"
        assert data["ID"] == "prod-abc-123"

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from mcp_cin7_core.mcp_server import resource_product_by_id

        await resource_product_by_id("prod-abc-123")

        mock_instance.aclose.assert_called_once()


# ----------------------------- Product By SKU -----------------------------


class TestProductBySku:
    """Tests for resource_product_by_sku()."""

    @pytest.mark.asyncio
    async def test_calls_get_product_with_sku(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from mcp_cin7_core.mcp_server import resource_product_by_sku

        result = await resource_product_by_sku("WIDGET-001")

        assert isinstance(result, str)
        mock_instance.get_product.assert_called_once_with(sku="WIDGET-001")

    @pytest.mark.asyncio
    async def test_returned_json_matches_mock_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from mcp_cin7_core.mcp_server import resource_product_by_sku

        result = await resource_product_by_sku("WIDGET-001")
        data = json.loads(result)

        assert data["SKU"] == "WIDGET-001"
        assert data["Name"] == "Blue Widget"
        assert data["Category"] == "Widgets"

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(return_value=PRODUCT_SINGLE)

        from mcp_cin7_core.mcp_server import resource_product_by_sku

        await resource_product_by_sku("WIDGET-001")

        mock_instance.aclose.assert_called_once()


# ----------------------------- Supplier Template -----------------------------


class TestSupplierTemplate:
    """Tests for resource_supplier_template()."""

    @pytest.mark.asyncio
    async def test_returns_valid_json_with_name_field(self):
        from mcp_cin7_core.mcp_server import resource_supplier_template

        result = await resource_supplier_template()
        template = json.loads(result)

        assert "Name" in template

    @pytest.mark.asyncio
    async def test_has_address_structure(self):
        from mcp_cin7_core.mcp_server import resource_supplier_template

        result = await resource_supplier_template()
        template = json.loads(result)

        assert "Address" in template
        address = template["Address"]
        for field in ("Line1", "City", "State", "Country"):
            assert field in address, f"Missing address field: {field}"


# ----------------------------- Supplier By ID -----------------------------


class TestSupplierById:
    """Tests for resource_supplier_by_id()."""

    @pytest.mark.asyncio
    async def test_calls_get_supplier_with_supplier_id(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from mcp_cin7_core.mcp_server import resource_supplier_by_id

        result = await resource_supplier_by_id("sup-abc-123")

        assert isinstance(result, str)
        mock_instance.get_supplier.assert_called_once_with(supplier_id="sup-abc-123")

    @pytest.mark.asyncio
    async def test_returned_json_matches_mock_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from mcp_cin7_core.mcp_server import resource_supplier_by_id

        result = await resource_supplier_by_id("sup-abc-123")
        data = json.loads(result)

        assert data["Name"] == "Acme Supplies"
        assert data["ID"] == "sup-abc-123"
        assert data["ContactPerson"] == "John Doe"

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from mcp_cin7_core.mcp_server import resource_supplier_by_id

        await resource_supplier_by_id("sup-abc-123")

        mock_instance.aclose.assert_called_once()


# ----------------------------- Supplier By Name -----------------------------


class TestSupplierByName:
    """Tests for resource_supplier_by_name()."""

    @pytest.mark.asyncio
    async def test_calls_get_supplier_with_name(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from mcp_cin7_core.mcp_server import resource_supplier_by_name

        result = await resource_supplier_by_name("Acme Supplies")

        assert isinstance(result, str)
        mock_instance.get_supplier.assert_called_once_with(name="Acme Supplies")

    @pytest.mark.asyncio
    async def test_returned_json_matches_mock_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from mcp_cin7_core.mcp_server import resource_supplier_by_name

        result = await resource_supplier_by_name("Acme Supplies")
        data = json.loads(result)

        assert data["Name"] == "Acme Supplies"
        assert data["Email"] == "john@acme-supplies.com"
        assert data["Currency"] == "USD"

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(return_value=SUPPLIER_SINGLE)

        from mcp_cin7_core.mcp_server import resource_supplier_by_name

        await resource_supplier_by_name("Acme Supplies")

        mock_instance.aclose.assert_called_once()


# ----------------------------- PO Template -----------------------------


class TestPOTemplate:
    """Tests for resource_purchase_order_template()."""

    @pytest.mark.asyncio
    async def test_returns_valid_json_with_required_fields(self):
        from mcp_cin7_core.mcp_server import resource_purchase_order_template

        result = await resource_purchase_order_template()
        template = json.loads(result)

        for field in ("Supplier", "Location", "OrderDate", "Lines"):
            assert field in template, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_lines_array_has_template_line_with_required_fields(self):
        from mcp_cin7_core.mcp_server import resource_purchase_order_template

        result = await resource_purchase_order_template()
        template = json.loads(result)

        assert isinstance(template["Lines"], list)
        assert len(template["Lines"]) >= 1

        line = template["Lines"][0]
        for field in ("ProductID", "SKU", "Name", "Quantity", "Price"):
            assert field in line, f"Missing line field: {field}"

    @pytest.mark.asyncio
    async def test_status_is_draft(self):
        from mcp_cin7_core.mcp_server import resource_purchase_order_template

        result = await resource_purchase_order_template()
        template = json.loads(result)

        assert template["Status"] == "DRAFT"


# ----------------------------- PO By ID -----------------------------


class TestPOById:
    """Tests for resource_purchase_order_by_id()."""

    @pytest.mark.asyncio
    async def test_calls_get_purchase_order_with_id(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_purchase_order = AsyncMock(return_value=PO_SINGLE)

        from mcp_cin7_core.mcp_server import resource_purchase_order_by_id

        result = await resource_purchase_order_by_id("po-abc-123")

        assert isinstance(result, str)
        mock_instance.get_purchase_order.assert_called_once_with(
            purchase_order_id="po-abc-123"
        )

    @pytest.mark.asyncio
    async def test_returned_json_matches_mock_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_purchase_order = AsyncMock(return_value=PO_SINGLE)

        from mcp_cin7_core.mcp_server import resource_purchase_order_by_id

        result = await resource_purchase_order_by_id("po-abc-123")
        data = json.loads(result)

        assert data["ID"] == "po-abc-123"
        assert data["Supplier"] == "Acme Supplies"
        assert data["Status"] == "DRAFT"
        assert data["Order"]["Lines"][0]["SKU"] == "WIDGET-001"

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_purchase_order = AsyncMock(return_value=PO_SINGLE)

        from mcp_cin7_core.mcp_server import resource_purchase_order_by_id

        await resource_purchase_order_by_id("po-abc-123")

        mock_instance.aclose.assert_called_once()


# ----------------------------- Sale Template -----------------------------


class TestSaleTemplate:
    """Tests for resource_sale_template()."""

    @pytest.mark.asyncio
    async def test_returns_valid_json_with_required_fields(self):
        from mcp_cin7_core.mcp_server import resource_sale_template

        result = await resource_sale_template()
        template = json.loads(result)

        for field in ("Customer", "Location", "Lines", "Status"):
            assert field in template, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_lines_array_has_template_line_with_required_fields(self):
        from mcp_cin7_core.mcp_server import resource_sale_template

        result = await resource_sale_template()
        template = json.loads(result)

        assert isinstance(template["Lines"], list)
        assert len(template["Lines"]) >= 1

        line = template["Lines"][0]
        for field in ("ProductID", "SKU", "Name", "Quantity", "Price"):
            assert field in line, f"Missing line field: {field}"

    @pytest.mark.asyncio
    async def test_status_is_draft(self):
        from mcp_cin7_core.mcp_server import resource_sale_template

        result = await resource_sale_template()
        template = json.loads(result)

        assert template["Status"] == "DRAFT"


# ----------------------------- Sale By ID -----------------------------


class TestSaleById:
    """Tests for resource_sale_by_id()."""

    @pytest.mark.asyncio
    async def test_calls_get_sale_with_sale_id(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_sale = AsyncMock(return_value=SALE_SINGLE)

        from mcp_cin7_core.mcp_server import resource_sale_by_id

        result = await resource_sale_by_id("sale-abc-123")

        assert isinstance(result, str)
        mock_instance.get_sale.assert_called_once_with(sale_id="sale-abc-123")

    @pytest.mark.asyncio
    async def test_returned_json_matches_mock_data(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_sale = AsyncMock(return_value=SALE_SINGLE)

        from mcp_cin7_core.mcp_server import resource_sale_by_id

        result = await resource_sale_by_id("sale-abc-123")
        data = json.loads(result)

        assert data["ID"] == "sale-abc-123"
        assert data["Customer"] == "Test Customer"
        assert data["Status"] == "DRAFT"
        assert data["Quote"]["Lines"][0]["SKU"] == "WIDGET-001"

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_sale = AsyncMock(return_value=SALE_SINGLE)

        from mcp_cin7_core.mcp_server import resource_sale_by_id

        await resource_sale_by_id("sale-abc-123")

        mock_instance.aclose.assert_called_once()


# ----------------------------- Resource Error Handling -----------------------------


class TestResourceErrorHandling:
    """Tests that resource handlers propagate exceptions and still call aclose()."""

    @pytest.mark.asyncio
    async def test_product_by_id_error_propagates_and_closes(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(side_effect=Exception("API error"))

        from mcp_cin7_core.mcp_server import resource_product_by_id

        with pytest.raises(Exception, match="API error"):
            await resource_product_by_id("prod-1")

        mock_instance.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_product_by_sku_error_propagates_and_closes(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_product = AsyncMock(side_effect=Exception("API error"))

        from mcp_cin7_core.mcp_server import resource_product_by_sku

        with pytest.raises(Exception, match="API error"):
            await resource_product_by_sku("SKU-1")

        mock_instance.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_supplier_by_id_error_propagates_and_closes(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(side_effect=Exception("API error"))

        from mcp_cin7_core.mcp_server import resource_supplier_by_id

        with pytest.raises(Exception, match="API error"):
            await resource_supplier_by_id("sup-1")

        mock_instance.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_supplier_by_name_error_propagates_and_closes(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_supplier = AsyncMock(side_effect=Exception("API error"))

        from mcp_cin7_core.mcp_server import resource_supplier_by_name

        with pytest.raises(Exception, match="API error"):
            await resource_supplier_by_name("Test")

        mock_instance.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_purchase_order_by_id_error_propagates_and_closes(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_purchase_order = AsyncMock(side_effect=Exception("API error"))

        from mcp_cin7_core.mcp_server import resource_purchase_order_by_id

        with pytest.raises(Exception, match="API error"):
            await resource_purchase_order_by_id("po-1")

        mock_instance.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_sale_by_id_error_propagates_and_closes(self, mock_cin7_class):
        mock_class, mock_instance = mock_cin7_class
        mock_instance.get_sale = AsyncMock(side_effect=Exception("API error"))

        from mcp_cin7_core.mcp_server import resource_sale_by_id

        with pytest.raises(Exception, match="API error"):
            await resource_sale_by_id("sale-1")

        mock_instance.aclose.assert_called_once()
