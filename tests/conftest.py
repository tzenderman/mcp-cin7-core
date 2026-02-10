"""Shared test fixtures for MCP Cin7 Core tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_cin7_core.cin7_client import Cin7Client


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
    """Create a Cin7Client with mocked httpx client."""
    with patch.dict("os.environ", {
        "CIN7_ACCOUNT_ID": "test_account",
        "CIN7_API_KEY": "test_key",
    }):
        client = Cin7Client.from_env()
        client.client = MagicMock()
        return client


@pytest.fixture
def mock_cin7_class():
    """Patch Cin7Client in mcp_server module, yield (mock_class, mock_instance).

    Usage:
        def test_something(mock_cin7_class):
            mock_class, mock_instance = mock_cin7_class
            mock_instance.some_method = AsyncMock(return_value={...})
            # call the tool function...
            mock_instance.aclose.assert_called_once()
    """
    with patch("mcp_cin7_core.mcp_server.Cin7Client") as mock_class:
        mock_instance = MagicMock()
        mock_instance.aclose = AsyncMock()
        mock_class.from_env.return_value = mock_instance
        yield mock_class, mock_instance
