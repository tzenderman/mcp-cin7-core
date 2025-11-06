from __future__ import annotations

import os
import logging
import time
import hashlib
import json
import base64
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx

from .mcp_server import server as mcp_server

load_dotenv()

logger = logging.getLogger("mcp_cin7_core.http_server")

# Token validation cache
# Maps SHA256(token) -> (user_info, expiry_timestamp)
# Note: Tokens are hashed before caching to prevent plaintext exposure
_token_cache: dict[str, tuple[dict, float]] = {}
TOKEN_CACHE_TTL = int(os.getenv("TOKEN_CACHE_TTL_SECONDS", "120"))  # 2 minutes default
TOKEN_CACHE_MAX_SIZE = int(os.getenv("TOKEN_CACHE_MAX_SIZE", "1000"))  # Prevent unbounded growth

# Create MCP streamable HTTP app first to initialize the session manager
# The MCP SDK configures the endpoint at /mcp by default (streamable_http_path setting)
mcp_app = mcp_server.streamable_http_app()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the FastAPI app and MCP session manager."""
    # Start the MCP session manager
    async with mcp_server.session_manager.run():
        logger.info("MCP session manager started")
        yield
    logger.info("MCP session manager stopped")

app = FastAPI(title="mcp-cin7-core", version="0.2.0", lifespan=lifespan)

# Add CORS middleware for MCP Inspector and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

# Auth0 OAuth Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")

# MCP Server Base URL (for OAuth resource identifier)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://mcp-cin7-core.onrender.com")


def _hash_token(token: str) -> str:
    """Hash token using SHA256 to prevent plaintext storage in cache."""
    return hashlib.sha256(token.encode()).hexdigest()


def _get_token_expiry(token: str) -> Optional[float]:
    """Extract expiry timestamp from JWT token if possible.

    Returns None if token is opaque (not JWT) or cannot be parsed.
    JWE tokens (encrypted JWTs from Auth0) cannot be decoded without the key,
    so this will return None for those.
    """
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Decode payload (add padding if needed)
        payload_b64 = parts[1]
        padding = '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_json)

        # Extract exp claim if present
        exp = payload.get('exp')
        if exp and isinstance(exp, (int, float)):
            return float(exp)

        return None
    except Exception:
        # Token is opaque or encrypted (JWE) - cannot parse
        return None


async def verify_oauth_token(token: str) -> Optional[dict]:
    """Verify Auth0 token using the /userinfo endpoint with caching.

    Auth0 does not support RFC 7662 token introspection. For opaque/JWE tokens
    (which Auth0 issues to dynamically registered clients like Claude Desktop),
    the recommended validation approach is to call the /userinfo endpoint.

    Security features:
    - Tokens are hashed (SHA256) before caching to prevent plaintext exposure
    - JWT expiry is checked if token is parseable
    - Cache TTL is minimum of TOKEN_CACHE_TTL_SECONDS and JWT expiry
    - Results cached for 2 minutes by default to avoid Auth0 rate limits

    Reference: https://community.auth0.com/t/opaque-token-validation-with-introspection-endpoint/37553
    """
    if not AUTH0_DOMAIN:
        logger.error("AUTH0_DOMAIN not configured")
        return None

    # Hash token to prevent plaintext storage
    token_hash = _hash_token(token)

    # Check if JWT has expired (if parseable)
    token_expiry = _get_token_expiry(token)
    now = time.time()

    if token_expiry:
        logger.debug(f"[VERIFY] Token has JWT expiry claim: {token_expiry} (current time: {now})")
        if now >= token_expiry:
            logger.warning("[VERIFY] ✗ Token has expired (JWT exp claim)")
            # Remove from cache if present
            _token_cache.pop(token_hash, None)
            return None
    else:
        logger.debug("[VERIFY] Token is opaque/JWE (no JWT exp claim)")

    # Check cache
    if token_hash in _token_cache:
        user_info, expiry = _token_cache[token_hash]
        if now < expiry:
            logger.debug(f"[VERIFY] ✓ Token validated from cache. User: {user_info.get('email', user_info.get('sub', 'unknown'))}")
            return user_info
        else:
            # Expired - remove from cache
            logger.debug("[VERIFY] Cached token expired, re-validating with Auth0")
            del _token_cache[token_hash]

    try:
        # Use Auth0's /userinfo endpoint to validate the token
        # Auth0 must validate the token before returning user info,
        # making this an indirect token validation mechanism
        userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
        logger.debug(f"[VERIFY] Calling Auth0 /userinfo endpoint: {userinfo_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )

            logger.debug(f"[VERIFY] Auth0 /userinfo response status: {response.status_code}")

            if response.status_code != 200:
                logger.warning(f"[VERIFY] ✗ Token validation via /userinfo failed with status {response.status_code}")
                logger.debug(f"[VERIFY] Response body: {response.text}")
                return None

            # Successfully retrieved user info - token is valid
            user_info = response.json()
            logger.info(f"[VERIFY] ✓ Token validated via Auth0. User: {user_info.get('email', user_info.get('sub', 'unknown'))}")

            # Calculate cache expiry: minimum of cache TTL and token expiry
            cache_expiry = now + TOKEN_CACHE_TTL
            if token_expiry:
                # Use the earlier of cache TTL or JWT expiry
                expiry = min(cache_expiry, token_expiry)
                ttl_used = int(expiry - now)
                logger.debug(f"JWT expires at {token_expiry}, cache TTL is {TOKEN_CACHE_TTL}s, using {ttl_used}s")
            else:
                # Opaque/JWE token - use cache TTL only
                expiry = cache_expiry
                logger.debug(f"Opaque token (no exp claim), using cache TTL of {TOKEN_CACHE_TTL}s")

            # Cache the result using hashed token as key
            _token_cache[token_hash] = (user_info, expiry)

            # Enforce cache size limit
            if len(_token_cache) > TOKEN_CACHE_MAX_SIZE:
                # First try removing expired entries
                expired_tokens = [
                    t for t, (_, exp) in _token_cache.items() if now >= exp
                ]
                for t in expired_tokens:
                    del _token_cache[t]
                logger.debug(f"Cleaned up {len(expired_tokens)} expired tokens from cache")

                # If still over limit, remove oldest (lowest expiry)
                if len(_token_cache) > TOKEN_CACHE_MAX_SIZE:
                    sorted_tokens = sorted(_token_cache.items(), key=lambda x: x[1][1])
                    tokens_to_remove = len(_token_cache) - TOKEN_CACHE_MAX_SIZE
                    for t, _ in sorted_tokens[:tokens_to_remove]:
                        del _token_cache[t]
                    logger.debug(f"Evicted {tokens_to_remove} tokens to enforce cache size limit")

            return user_info

    except Exception as e:
        logger.error(f"OAuth verification error: {e}")
        return None

@app.get("/health")
async def health():
    """Health check endpoint with token cache statistics."""
    now = time.time()
    active_tokens = sum(1 for _, exp in _token_cache.values() if now < exp)

    return {
        "status": "ok",
        "transport": "streamable-http",
        "token_cache": {
            "size": len(_token_cache),
            "active": active_tokens,
            "ttl_seconds": TOKEN_CACHE_TTL,
            "max_size": TOKEN_CACHE_MAX_SIZE
        }
    }


@app.get("/.well-known/mcp-oauth")
async def oauth_discovery():
    """OAuth discovery endpoint for MCP clients (Claude Desktop).

    This endpoint allows Claude Desktop to auto-discover OAuth configuration
    when adding the server as a remote connector.
    """
    if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID:
        return Response(
            status_code=501,
            content="OAuth not configured on this server"
        )

    return {
        "authorizationEndpoint": f"https://{AUTH0_DOMAIN}/authorize",
        "tokenEndpoint": f"https://{AUTH0_DOMAIN}/oauth/token",
        "clientId": AUTH0_CLIENT_ID,
        "audience": AUTH0_AUDIENCE if AUTH0_AUDIENCE else None,
        "scopes": ["openid", "profile", "email", "offline_access"]
    }

# --------------------------------------------------------------------------- #
# RFC 8414 / .well-known OAuth 2.0 metadata – required by some MCP clients
# --------------------------------------------------------------------------- #

@app.get("/.well-known/oauth-authorization-server")
@app.get("/.well-known/oauth-authorization-server/mcp")
async def oauth_server_metadata():
    """Return OAuth 2.0 Authorization Server metadata.

    Claude Desktop queries these endpoints before starting the OAuth flow.
    We map them to our Auth0 tenant so the client can discover endpoints.
    """
    if not AUTH0_DOMAIN:
        return Response(status_code=501, content="OAuth not configured on this server")

    metadata = {
        "issuer": f"https://{AUTH0_DOMAIN}/",
        "authorization_endpoint": f"https://{AUTH0_DOMAIN}/authorize",
        "token_endpoint": f"https://{AUTH0_DOMAIN}/oauth/token",
        "jwks_uri": f"https://{AUTH0_DOMAIN}/.well-known/jwks.json",
        # REMOVED: registration_endpoint - forces clients to use configured client_id
        # instead of dynamically registering new applications
        "client_id": AUTH0_CLIENT_ID,  # Claude Desktop needs this to know which client to use
        "audience": AUTH0_AUDIENCE if AUTH0_AUDIENCE else None,  # Required for Auth0 API tokens
        "scopes_supported": ["openid", "profile", "email", "offline_access"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
    }
    return metadata


@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_resource_metadata():
    """Return minimal OAuth 2.0 Resource Server metadata required by clients."""
    if not AUTH0_DOMAIN:
        return Response(status_code=501, content="OAuth not configured on this server")

    return {
        "resource": MCP_SERVER_URL,
        "scopes_supported": ["openid", "profile", "email", "offline_access"],
        "authorization_servers": [f"https://{AUTH0_DOMAIN}/"],  # Must match issuer URL exactly (with trailing slash)
        # REMOVED: registration_endpoint - forces clients to use configured client_id
    }

# --------------------------------------------------------------------------- #
# Verbose request logger – logs every request/response when MCP_LOG_LEVEL=DEBUG
# This is placed BEFORE the auth middleware so we capture even unauthorized
# attempts. Enable by setting the env var MCP_LOG_LEVEL=DEBUG on Render.
# --------------------------------------------------------------------------- #

@app.middleware("http")
async def log_requests(request: Request, call_next):  # noqa: D401
    """Log inbound and outbound HTTP traffic when logger is in DEBUG mode."""
    if logger.isEnabledFor(logging.DEBUG):
        headers = {k: v for k, v in request.headers.items()}
        logger.debug("↘︎ %s %s headers=%s client=%s", request.method, request.url.path, headers, request.client.host)

    response: Response = await call_next(request)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("↗︎ %s %s → %s", request.method, request.url.path, response.status_code)

    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth for health check, OAuth discovery, and CORS preflight
    public_paths = [
        "/health",
        "/.well-known/mcp-oauth",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-authorization-server/mcp",
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp"
    ]
    if request.url.path in public_paths or request.method == "OPTIONS":
        return await call_next(request)

    # Require OAuth for /mcp endpoints
    if request.url.path.startswith("/mcp"):
        if not AUTH0_DOMAIN:
            logger.error("AUTH0_DOMAIN not configured - OAuth required")
            return Response(status_code=500, content="Server misconfigured")

        # Detailed logging for token debugging
        auth_header = request.headers.get("Authorization", "")
        logger.debug(f"[AUTH] Request to {request.url.path} from {request.client.host}")
        logger.debug(f"[AUTH] Authorization header present: {bool(auth_header)}")

        if auth_header:
            # Show header format (redacted)
            header_prefix = auth_header[:20] + "..." if len(auth_header) > 20 else auth_header
            logger.debug(f"[AUTH] Authorization header format: {header_prefix}")
            logger.debug(f"[AUTH] Header starts with 'Bearer ': {auth_header.startswith('Bearer ')}")

        token = auth_header.replace("Bearer ", "").strip()

        if not token:
            logger.warning("[AUTH] ✗ No authorization token provided")
            logger.debug(f"[AUTH] Full header value (empty?): '{auth_header}'")
            # Return 401 with WWW-Authenticate header to trigger OAuth flow
            return Response(
                status_code=401,
                content="Unauthorized - No token",
                headers={
                    "WWW-Authenticate": f'Bearer, resource_metadata_uri="{MCP_SERVER_URL}/.well-known/oauth-protected-resource/mcp"'
                }
            )

        # Verify OAuth token
        logger.debug(f"[AUTH] Validating OAuth token for request from {request.client.host}")
        logger.debug(f"[AUTH] Token length: {len(token)} chars")
        logger.debug(f"[AUTH] Token preview (first 50 chars): {token[:50]}...")

        payload = await verify_oauth_token(token)

        if not payload:
            logger.warning(f"[AUTH] ✗ OAuth token validation FAILED from {request.client.host}")
            return Response(
                status_code=401,
                content="Unauthorized",
                headers={
                    "WWW-Authenticate": f'Bearer, error="invalid_token", error_description="The access token is invalid or has expired."'
                }
            )

        # Successfully authenticated
        email = payload.get("email", "unknown")
        logger.info(f"[AUTH] ✓ OAuth authenticated: {email}")
        return await call_next(request)

    return await call_next(request)

# Mount MCP app at root so the /mcp endpoint is accessible at /mcp
app.mount("/", mcp_app)


def main() -> None:
    """Entrypoint for MCP HTTP server."""
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
