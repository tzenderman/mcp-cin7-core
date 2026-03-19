"""Tests for MCP server prompt functions."""

from __future__ import annotations

import pytest


class TestCreateProductPrompt:
    """Tests for the create_product prompt."""

    async def test_returns_non_empty_string(self):
        from cin7_core_server.resources.prompts import create_product

        result = await create_product()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_mentions_required_fields(self):
        from cin7_core_server.resources.prompts import create_product

        result = await create_product()
        assert "SKU" in result
        assert "Name" in result
        assert "Category" in result
        assert "DefaultLocation" in result

    async def test_mentions_template_resource(self):
        from cin7_core_server.resources.prompts import create_product

        result = await create_product()
        assert "cin7://templates/product" in result


class TestUpdateBatchPrompt:
    """Tests for the update_batch prompt."""

    async def test_returns_non_empty_string(self):
        from cin7_core_server.resources.prompts import update_batch

        result = await update_batch()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_mentions_error_handling(self):
        from cin7_core_server.resources.prompts import update_batch

        result = await update_batch()
        lower = result.lower()
        assert "error" in lower
        assert "continue" in lower or "failures" in lower
        assert "report" in lower or "summary" in lower

    async def test_mentions_approval_from_user(self):
        from cin7_core_server.resources.prompts import update_batch

        result = await update_batch()
        assert "approval" in result.lower()


class TestVerifyRequiredFieldsPrompt:
    """Tests for the verify_required_fields prompt."""

    async def test_returns_non_empty_string(self):
        from cin7_core_server.resources.prompts import verify_required_fields

        result = await verify_required_fields()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_mentions_all_required_fields(self):
        from cin7_core_server.resources.prompts import verify_required_fields

        result = await verify_required_fields()
        assert "SKU" in result
        assert "Name" in result
        assert "Category" in result
        assert "Status" in result
        assert "Type" in result
        assert "UOM" in result
        assert "CostingMethod" in result
        assert "DefaultLocation" in result


class TestCreatePurchaseOrderPrompt:
    """Tests for the create_purchase_order prompt."""

    async def test_returns_non_empty_string(self):
        from cin7_core_server.resources.prompts import create_purchase_order

        result = await create_purchase_order()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_mentions_po_specific_fields(self):
        from cin7_core_server.resources.prompts import create_purchase_order

        result = await create_purchase_order()
        assert "Supplier" in result
        assert "Location" in result
        assert "OrderDate" in result
        assert "Lines" in result

    async def test_mentions_draft_status(self):
        from cin7_core_server.resources.prompts import create_purchase_order

        result = await create_purchase_order()
        assert "DRAFT" in result


class TestCreateSalePrompt:
    """Tests for the create_sale prompt."""

    async def test_returns_non_empty_string(self):
        from cin7_core_server.resources.prompts import create_sale

        result = await create_sale()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_mentions_sale_specific_fields(self):
        from cin7_core_server.resources.prompts import create_sale

        result = await create_sale()
        assert "Customer" in result
        assert "Location" in result
        assert "Lines" in result

    async def test_mentions_draft_status(self):
        from cin7_core_server.resources.prompts import create_sale

        result = await create_sale()
        assert "DRAFT" in result
