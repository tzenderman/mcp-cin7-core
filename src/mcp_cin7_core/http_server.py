from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from jose import jwt, JWTError
import httpx

from .mcp_server import server as mcp_server

load_dotenv()

logger = logging.getLogger("mcp_cin7_core.http_server")

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
AUTH0_ALGORITHMS = ["RS256"]


async def verify_oauth_token(token: str) -> Optional[dict]:
    """Verify Auth0 JWT token."""
    if not AUTH0_DOMAIN:
        return None
        
    try:
        # Get Auth0 public keys (JWKS)
        jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
        
        # Fetch JWKS
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            jwks = response.json()
        
        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        
        if not rsa_key:
            logger.warning("No matching key found in JWKS")
            return None
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        return payload
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"OAuth verification error: {e}")
        return None

@app.get("/health")
async def health():
    return {"status": "ok", "transport": "streamable-http"}


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
        "scopes": ["openid", "profile", "email"]
    }

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth for health check, OAuth discovery, and CORS preflight
    if request.url.path in ["/health", "/.well-known/mcp-oauth"] or request.method == "OPTIONS":
        return await call_next(request)

    # Require OAuth for /mcp endpoints
    if request.url.path.startswith("/mcp"):
        if not AUTH0_DOMAIN:
            logger.error("AUTH0_DOMAIN not configured - OAuth required")
            return Response(status_code=500, content="Server misconfigured")
        
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()

        if not token:
            logger.warning("No authorization token provided")
            return Response(status_code=401, content="Unauthorized - No token")

        # Verify OAuth token
        logger.debug(f"Validating OAuth token for request from {request.client.host}")
        payload = await verify_oauth_token(token)
        
        if not payload:
            logger.warning(f"✗ OAuth authentication failed from {request.client.host}")
            return Response(status_code=401, content="Unauthorized")
        
        # Successfully authenticated
        email = payload.get("email", "unknown")
        logger.info(f"✓ OAuth authenticated: {email}")
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
