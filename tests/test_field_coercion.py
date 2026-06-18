"""Tests for FieldList string-to-list coercion.

MCP clients may send the ``fields`` parameter as a JSON-encoded string
(e.g. ``'["PriceTier1"]'``) instead of a native list when the JSON Schema
lacks ``type: array``. These tests verify that the ``FieldList`` type
coerces all known client formats into ``list[str]``.

See bug report: "fields parameter rejected — server receives string, validator
requires list."
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter

from cin7_core_server.utils.fields import FieldList, _coerce_field_list


class TestCoerceFieldList:
    """Unit tests for the _coerce_field_list validator function."""

    def test_none_passthrough(self):
        assert _coerce_field_list(None) is None

    def test_native_list_passthrough(self):
        result = _coerce_field_list(["PriceTier1", "PurchasePrice"])
        assert result == ["PriceTier1", "PurchasePrice"]

    def test_empty_list_passthrough(self):
        result = _coerce_field_list([])
        assert result == []

    def test_json_array_string(self):
        """Client sends '["SKU", "Name", "PriceTier1"]' as a string."""
        result = _coerce_field_list('["SKU", "Name", "PriceTier1"]')
        assert result == ["SKU", "Name", "PriceTier1"]

    def test_json_single_item_array(self):
        """Client sends '["PriceTier1"]' as a string."""
        result = _coerce_field_list('["PriceTier1"]')
        assert result == ["PriceTier1"]

    def test_json_wildcard_array(self):
        """Client sends '["*"]' as a string."""
        result = _coerce_field_list('["*"]')
        assert result == ["*"]

    def test_bare_string_single_field(self):
        """Client sends 'PriceTier1' as a bare string."""
        result = _coerce_field_list("PriceTier1")
        assert result == ["PriceTier1"]

    def test_bare_wildcard(self):
        """Client sends '*' as a bare string."""
        result = _coerce_field_list("*")
        assert result == ["*"]

    def test_comma_separated(self):
        """Client sends 'PriceTier1,PurchasePrice' as a string."""
        result = _coerce_field_list("PriceTier1,PurchasePrice")
        assert result == ["PriceTier1", "PurchasePrice"]

    def test_comma_separated_with_spaces(self):
        """Client sends 'PriceTier1, PurchasePrice, Brand' with spaces."""
        result = _coerce_field_list("PriceTier1, PurchasePrice, Brand")
        assert result == ["PriceTier1", "PurchasePrice", "Brand"]

    def test_empty_string_returns_none(self):
        result = _coerce_field_list("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = _coerce_field_list("   ")
        assert result is None

    def test_json_array_with_whitespace(self):
        """Client sends ' ["PriceTier1"] ' with surrounding whitespace."""
        result = _coerce_field_list(' ["PriceTier1"] ')
        assert result == ["PriceTier1"]


class TestFieldListJsonSchema:
    """Verify JSON Schema output includes type: array."""

    def test_schema_has_array_type(self):
        ta = TypeAdapter(FieldList)
        schema = ta.json_schema()
        # Should have anyOf with array and null
        assert "anyOf" in schema
        types = [s.get("type") for s in schema["anyOf"]]
        assert "array" in types

    def test_schema_items_are_string(self):
        ta = TypeAdapter(FieldList)
        schema = ta.json_schema()
        array_schema = next(s for s in schema["anyOf"] if s.get("type") == "array")
        assert array_schema["items"]["type"] == "string"


class TestFieldListPydanticValidation:
    """End-to-end: verify pydantic validates/coerces all input forms."""

    @pytest.fixture
    def adapter(self):
        return TypeAdapter(FieldList)

    def test_validates_native_list(self, adapter):
        result = adapter.validate_python(["PriceTier1"])
        assert result == ["PriceTier1"]

    def test_validates_none(self, adapter):
        result = adapter.validate_python(None)
        assert result is None

    def test_coerces_json_string(self, adapter):
        result = adapter.validate_python('["PriceTier1", "PurchasePrice"]')
        assert result == ["PriceTier1", "PurchasePrice"]

    def test_coerces_bare_string(self, adapter):
        result = adapter.validate_python("PriceTier1")
        assert result == ["PriceTier1"]

    def test_coerces_comma_separated(self, adapter):
        result = adapter.validate_python("PriceTier1,PurchasePrice")
        assert result == ["PriceTier1", "PurchasePrice"]

    def test_coerces_wildcard(self, adapter):
        result = adapter.validate_python("*")
        assert result == ["*"]
