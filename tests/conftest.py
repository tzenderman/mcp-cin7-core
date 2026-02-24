"""Shared test fixtures for MCP Cin7 Core tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cin7_core_server.cin7_client import Cin7Client


@pytest.fixture
def mock_response():
    """Factory for creating mock HTTP responses.

    Usage:
        resp = mock_response(200, {"key": "value"})
        resp = mock_response(401, text="Unauthorized")
    """
    def _make(status_code=200, json_data=None, text=None, headers=None):
        response = MagicMock()
        response.status_code = status_code
        if json_data is not None:
            response.json.return_value = json_data
            response.text = text or str(json_data)
        else:
            response.json.side_effect = ValueError("No JSON")
            response.text = text or ""
        response.headers = headers or {}
        return response
    return _make


@pytest.fixture
def mock_client():
    """Create a Cin7Client with mocked _request method."""
    with patch.dict("os.environ", {
        "CIN7_ACCOUNT_ID": "test_account",
        "CIN7_API_KEY": "test_key",
    }):
        client = Cin7Client.from_env()
        client._request = AsyncMock()
        return client


# All resource modules that import Cin7Client
_RESOURCE_MODULES = [
    "cin7_core_server.resources.auth",
    "cin7_core_server.resources.products",
    "cin7_core_server.resources.suppliers",
    "cin7_core_server.resources.sales",
    "cin7_core_server.resources.purchase_orders",
    "cin7_core_server.resources.stock",
    "cin7_core_server.resources.snapshots",
    "cin7_core_server.resources.templates",
]


@pytest.fixture
def mock_cin7_class():
    """Patch Cin7Client in all resource modules, yield (mock_class, mock_instance).

    Usage:
        def test_something(mock_cin7_class):
            mock_class, mock_instance = mock_cin7_class
            mock_instance.some_method = AsyncMock(return_value={...})
            # call the tool function...
    """
    mock_instance = MagicMock()
    mock_instance.aclose = AsyncMock()
    mock_class = MagicMock()
    mock_class.from_env.return_value = mock_instance

    patchers = [patch(f"{mod}.Cin7Client", mock_class) for mod in _RESOURCE_MODULES]
    for p in patchers:
        p.start()
    yield mock_class, mock_instance
    for p in patchers:
        p.stop()
