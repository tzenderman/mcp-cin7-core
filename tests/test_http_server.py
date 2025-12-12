"""Tests for HTTP server with mocked ScaleKit client."""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


@pytest.fixture
def mock_scalekit_client():
    """Create a mock ScaleKit client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def app_with_mocked_scalekit(mock_scalekit_client):
    """Create app with mocked ScaleKit client and patched module-level variables."""
    with patch("mcp_cin7_core.http_server.ScalekitClient") as mock_class:
        mock_class.return_value = mock_scalekit_client

        # Patch the module-level variables that were read at import time
        with patch("mcp_cin7_core.http_server.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
             patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_ID", "test_client_id"), \
             patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
             patch("mcp_cin7_core.http_server.SCALEKIT_RESOURCE_ID", "res_test"), \
             patch("mcp_cin7_core.http_server.SERVER_URL", "https://test.example.com"), \
             patch("mcp_cin7_core.http_server.ALLOWED_EMAILS", {"allowed@example.com", "admin@test.com"}), \
             patch("mcp_cin7_core.http_server.SCALEKIT_INTERCEPTOR_SECRET", None):

            # Reset the global client so it gets re-initialized with mock
            import mcp_cin7_core.http_server as http_server
            http_server._scalekit_client = None

            from mcp_cin7_core.http_server import app
            yield app, mock_scalekit_client


@pytest.fixture
def client(app_with_mocked_scalekit):
    """Create test client with mocked ScaleKit."""
    app, _ = app_with_mocked_scalekit
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["transport"] == "streamable-http"
        assert data["oauth_provider"] == "scalekit"


class TestOAuthMetadata:
    """Tests for OAuth protected resource metadata."""

    def test_oauth_metadata_returns_resource_info(self, client):
        """OAuth metadata should return resource and authorization servers."""
        response = client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        data = response.json()
        assert "resource" in data
        assert "authorization_servers" in data
        assert "bearer_methods_supported" in data
        assert "scopes_supported" in data


class TestMCPEndpointAuth:
    """Tests for MCP endpoint authentication."""

    def test_mcp_requires_auth(self, client):
        """MCP endpoint should require authentication."""
        response = client.post("/mcp", json={})
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_mcp_rejects_invalid_token(self, app_with_mocked_scalekit):
        """MCP endpoint should reject invalid tokens."""
        app, mock_client = app_with_mocked_scalekit
        mock_client.validate_token.side_effect = Exception("Invalid token")

        client = TestClient(app)
        response = client.post(
            "/mcp",
            json={},
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_mcp_auth_passes_with_valid_token(self, app_with_mocked_scalekit):
        """MCP endpoint should pass auth middleware with valid token.

        Note: We don't test the full MCP request here since that requires
        proper lifespan management. We just verify auth middleware passes.
        """
        app, mock_client = app_with_mocked_scalekit
        mock_client.validate_token.return_value = {
            "sub": "user123",
            "email": "user@example.com"
        }

        # We verify the token validation was called (auth middleware passed)
        # The MCP endpoint itself may fail due to lifespan, but that's separate
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Authorization": "Bearer valid_token"}
        )
        # Should NOT be 401 - auth passed, even if MCP handling fails (500)
        assert response.status_code != 401
        # Verify the token was validated
        mock_client.validate_token.assert_called_once()


class TestInterceptorPreSignup:
    """Tests for PRE_SIGNUP interceptor."""

    def test_allows_email_in_allowlist(self, client):
        """Should allow emails that are in the allowlist."""
        payload = {
            "interceptor_context": {
                "user_email": "allowed@example.com"
            }
        }
        response = client.post(
            "/auth/interceptors/pre-signup",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "ALLOW"

    def test_denies_email_not_in_allowlist(self, client):
        """Should deny emails not in the allowlist."""
        payload = {
            "interceptor_context": {
                "user_email": "notallowed@example.com"
            }
        }
        response = client.post(
            "/auth/interceptors/pre-signup",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "DENY"
        assert "error" in data

    def test_handles_case_insensitive_email(self, client):
        """Should handle email comparison case-insensitively."""
        payload = {
            "interceptor_context": {
                "user_email": "ALLOWED@EXAMPLE.COM"
            }
        }
        response = client.post(
            "/auth/interceptors/pre-signup",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "ALLOW"

    def test_rejects_invalid_json(self, client):
        """Should reject invalid JSON payload."""
        response = client.post(
            "/auth/interceptors/pre-signup",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestInterceptorPreSessionCreate:
    """Tests for PRE_SESSION_CREATION interceptor."""

    def test_allows_email_in_allowlist(self, client):
        """Should allow emails that are in the allowlist."""
        payload = {
            "interceptor_context": {
                "user_email": "admin@test.com"
            }
        }
        response = client.post(
            "/auth/interceptors/pre-session-create",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "ALLOW"
        assert "response" in data
        assert data["response"]["claims"]["cin7_access"] == "granted"

    def test_denies_email_not_in_allowlist(self, client):
        """Should deny emails not in the allowlist."""
        payload = {
            "interceptor_context": {
                "user_email": "blocked@example.com"
            }
        }
        response = client.post(
            "/auth/interceptors/pre-session-create",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "DENY"
        assert "error" in data


class TestInterceptorSignatureVerification:
    """Tests for interceptor signature verification."""

    def test_rejects_invalid_signature_when_secret_configured(self):
        """Should reject requests with invalid signature when secret is set."""
        mock_client = MagicMock()
        # SDK's verify_interceptor_payload raises exception on invalid signature
        mock_client.verify_interceptor_payload.side_effect = Exception("Invalid signature")

        with patch("mcp_cin7_core.http_server.ScalekitClient") as mock_class:
            mock_class.return_value = mock_client

            with patch("mcp_cin7_core.http_server.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_ID", "test_client_id"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_RESOURCE_ID", "res_test"), \
                 patch("mcp_cin7_core.http_server.SERVER_URL", "https://test.example.com"), \
                 patch("mcp_cin7_core.http_server.ALLOWED_EMAILS", {"allowed@example.com"}), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_INTERCEPTOR_SECRET", "test_secret_123"):

                import mcp_cin7_core.http_server as http_server
                http_server._scalekit_client = None

                client = TestClient(http_server.app)
                payload = {
                    "interceptor_context": {
                        "user_email": "allowed@example.com"
                    }
                }
                response = client.post(
                    "/auth/interceptors/pre-signup",
                    json=payload,
                    headers={
                        "interceptor-id": "test_id",
                        "interceptor-signature": "invalid_signature",
                        "interceptor-timestamp": "1234567890",
                    }
                )
                assert response.status_code == 401
                # Verify the SDK method was called
                mock_client.verify_interceptor_payload.assert_called_once()

    def test_accepts_valid_signature_when_secret_configured(self):
        """Should accept requests with valid signature when secret is set."""
        mock_client = MagicMock()
        # SDK's verify_interceptor_payload returns None on success (no exception)
        mock_client.verify_interceptor_payload.return_value = None

        with patch("mcp_cin7_core.http_server.ScalekitClient") as mock_class:
            mock_class.return_value = mock_client

            with patch("mcp_cin7_core.http_server.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_ID", "test_client_id"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_RESOURCE_ID", "res_test"), \
                 patch("mcp_cin7_core.http_server.SERVER_URL", "https://test.example.com"), \
                 patch("mcp_cin7_core.http_server.ALLOWED_EMAILS", {"allowed@example.com"}), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_INTERCEPTOR_SECRET", "test_secret_123"):

                import mcp_cin7_core.http_server as http_server
                http_server._scalekit_client = None

                client = TestClient(http_server.app)
                payload = {
                    "interceptor_context": {
                        "user_email": "allowed@example.com"
                    }
                }
                response = client.post(
                    "/auth/interceptors/pre-signup",
                    json=payload,
                    headers={
                        "interceptor-id": "test_id",
                        "interceptor-signature": "valid_signature",
                        "interceptor-timestamp": "1234567890",
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert data["decision"] == "ALLOW"
                # Verify the SDK method was called
                mock_client.verify_interceptor_payload.assert_called_once()


class TestEmptyAllowlist:
    """Tests when no email allowlist is configured (allow all)."""

    def test_allows_any_email_when_no_allowlist(self):
        """Should allow any email when ALLOWED_EMAILS is empty."""
        with patch("mcp_cin7_core.http_server.ScalekitClient"):
            with patch("mcp_cin7_core.http_server.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_ID", "test_client_id"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_RESOURCE_ID", "res_test"), \
                 patch("mcp_cin7_core.http_server.SERVER_URL", "https://test.example.com"), \
                 patch("mcp_cin7_core.http_server.ALLOWED_EMAILS", set()), \
                 patch("mcp_cin7_core.http_server.SCALEKIT_INTERCEPTOR_SECRET", None):

                import mcp_cin7_core.http_server as http_server
                http_server._scalekit_client = None

                client = TestClient(http_server.app)
                payload = {
                    "interceptor_context": {
                        "user_email": "anyone@anywhere.com"
                    }
                }
                response = client.post(
                    "/auth/interceptors/pre-signup",
                    json=payload
                )
                assert response.status_code == 200
                data = response.json()
                assert data["decision"] == "ALLOW"
