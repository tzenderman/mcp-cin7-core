"""Tests for HTTP server with mocked ScaleKit client."""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from starlette.testclient import TestClient


@pytest.fixture
def mock_scalekit_client():
    """Create a mock ScaleKit client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def app_with_mocked_scalekit(mock_scalekit_client):
    """Create app with mocked ScaleKit client and patched module-level variables."""
    with patch("cin7_core_server.server_http.ScalekitClient") as mock_class:
        mock_class.return_value = mock_scalekit_client

        # Patch the module-level variables that were read at import time
        with patch("cin7_core_server.server_http.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_ID", "test_client_id"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
             patch("cin7_core_server.server_http.SCALEKIT_RESOURCE_ID", "res_test"), \
             patch("cin7_core_server.server_http.SERVER_URL", "https://test.example.com"), \
             patch("cin7_core_server.server_http.ALLOWED_EMAILS", {"allowed@example.com", "admin@test.com"}), \
             patch("cin7_core_server.server_http.SCALEKIT_INTERCEPTOR_SECRET", None):

            from cin7_core_server.server_http import app
            yield app, mock_scalekit_client


@pytest.fixture
def client(app_with_mocked_scalekit):
    """Create test client with mocked ScaleKit."""
    app, _ = app_with_mocked_scalekit
    return TestClient(app)


@pytest.fixture
def app_with_real_auth():
    """Create app with real ScalekitProvider and mocked token verifier.

    Uses FastMCP's built-in OAuth routes and auth middleware so tests
    exercise the real auth stack rather than mocking around it.
    """
    from fastmcp.server.auth.providers.scalekit import ScalekitProvider
    from cin7_core_server.server import create_mcp_server

    mock_verifier = AsyncMock()
    mock_verifier.required_scopes = ["cin7:read", "cin7:write"]
    mock_verifier.verify_token = AsyncMock(return_value=None)

    provider = ScalekitProvider(
        environment_url="https://test.scalekit.com",
        resource_id="res_test",
        base_url="https://test.example.com",
        token_verifier=mock_verifier,
    )

    mcp = create_mcp_server(auth=provider)
    app = mcp.http_app()

    return app, mock_verifier


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

    def test_oauth_metadata_returns_resource_info(self, app_with_real_auth):
        """OAuth metadata should return resource and authorization servers."""
        app, _ = app_with_real_auth
        client = TestClient(app)
        response = client.get("/.well-known/oauth-protected-resource/mcp")
        assert response.status_code == 200
        data = response.json()
        assert "resource" in data
        assert "authorization_servers" in data
        assert "bearer_methods_supported" in data
        assert "scopes_supported" in data


class TestMCPEndpointAuth:
    """Tests for MCP endpoint authentication."""

    def test_mcp_requires_auth(self, app_with_real_auth):
        """MCP endpoint should require authentication."""
        app, _ = app_with_real_auth
        client = TestClient(app)
        response = client.post("/mcp", json={})
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_mcp_rejects_invalid_token(self, app_with_real_auth):
        """MCP endpoint should reject invalid tokens."""
        app, mock_verifier = app_with_real_auth
        # verify_token returns None by default (from fixture) → token rejected
        client = TestClient(app)
        response = client.post(
            "/mcp",
            json={},
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_mcp_auth_passes_with_valid_token(self, app_with_real_auth):
        """MCP endpoint should pass auth middleware with valid token.

        Note: We don't test the full MCP request here since that requires
        proper lifespan management. We just verify auth middleware passes.
        """
        from fastmcp.server.auth.auth import AccessToken

        app, mock_verifier = app_with_real_auth
        mock_verifier.verify_token = AsyncMock(return_value=AccessToken(
            token="valid_token",
            client_id="test_client",
            scopes=["cin7:read"],
            expires_at=None,
        ))

        # The MCP endpoint itself may fail due to lifespan, but that's separate
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            headers={"Authorization": "Bearer valid_token"}
        )
        # Should NOT be 401 - auth passed, even if MCP handling fails
        assert response.status_code != 401
        mock_verifier.verify_token.assert_called_once()


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
        """Should return 500 for invalid JSON payload (fail closed)."""
        response = client.post(
            "/auth/interceptors/pre-signup",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 500
        data = response.json()
        assert data["decision"] == "DENY"


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
            "/auth/interceptors/pre-session-creation",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "ALLOW"

    def test_denies_email_not_in_allowlist(self, client):
        """Should deny emails not in the allowlist."""
        payload = {
            "interceptor_context": {
                "user_email": "blocked@example.com"
            }
        }
        response = client.post(
            "/auth/interceptors/pre-session-creation",
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
        mock_client.verify_interceptor_payload.side_effect = Exception("Invalid signature")

        with patch("cin7_core_server.server_http.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_ID", "test_client_id"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
             patch("cin7_core_server.server_http.SCALEKIT_RESOURCE_ID", "res_test"), \
             patch("cin7_core_server.server_http.SERVER_URL", "https://test.example.com"), \
             patch("cin7_core_server.server_http.ALLOWED_EMAILS", {"allowed@example.com"}), \
             patch("cin7_core_server.server_http.SCALEKIT_INTERCEPTOR_SECRET", "test_secret_123"), \
             patch("cin7_core_server.server_http.scalekit_client", mock_client):

            from cin7_core_server.server_http import app
            client = TestClient(app)
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
            mock_client.verify_interceptor_payload.assert_called_once()

    def test_accepts_valid_signature_when_secret_configured(self):
        """Should accept requests with valid signature when secret is set."""
        mock_client = MagicMock()
        mock_client.verify_interceptor_payload.return_value = True

        with patch("cin7_core_server.server_http.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_ID", "test_client_id"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
             patch("cin7_core_server.server_http.SCALEKIT_RESOURCE_ID", "res_test"), \
             patch("cin7_core_server.server_http.SERVER_URL", "https://test.example.com"), \
             patch("cin7_core_server.server_http.ALLOWED_EMAILS", {"allowed@example.com"}), \
             patch("cin7_core_server.server_http.SCALEKIT_INTERCEPTOR_SECRET", "test_secret_123"), \
             patch("cin7_core_server.server_http.scalekit_client", mock_client):

            from cin7_core_server.server_http import app
            client = TestClient(app)
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
            mock_client.verify_interceptor_payload.assert_called_once()


class TestEmptyAllowlist:
    """Tests when no email allowlist is configured (allow all)."""

    def test_allows_any_email_when_no_allowlist(self):
        """Should allow any email when ALLOWED_EMAILS is empty."""
        with patch("cin7_core_server.server_http.SCALEKIT_ENVIRONMENT_URL", "https://test.scalekit.com"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_ID", "test_client_id"), \
             patch("cin7_core_server.server_http.SCALEKIT_CLIENT_SECRET", "test_client_secret"), \
             patch("cin7_core_server.server_http.SCALEKIT_RESOURCE_ID", "res_test"), \
             patch("cin7_core_server.server_http.SERVER_URL", "https://test.example.com"), \
             patch("cin7_core_server.server_http.ALLOWED_EMAILS", set()), \
             patch("cin7_core_server.server_http.SCALEKIT_INTERCEPTOR_SECRET", None):

            from cin7_core_server.server_http import app
            client = TestClient(app)
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
