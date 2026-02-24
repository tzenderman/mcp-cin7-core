"""HTTP transport entry point with ScaleKit OAuth 2.1 authentication."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastmcp.server.auth.providers.scalekit import ScalekitProvider
from scalekit import ScalekitClient
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, Mount

from .server import create_mcp_server

load_dotenv()

# Configure logging
log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("cin7_core_server.server_http")

# ScaleKit Configuration
SCALEKIT_ENVIRONMENT_URL = os.getenv("SCALEKIT_ENVIRONMENT_URL")
SCALEKIT_CLIENT_ID = os.getenv("SCALEKIT_CLIENT_ID", "")
SCALEKIT_CLIENT_SECRET = os.getenv("SCALEKIT_CLIENT_SECRET", "")
SCALEKIT_RESOURCE_ID = os.getenv("SCALEKIT_RESOURCE_ID")
SCALEKIT_INTERCEPTOR_SECRET = os.getenv("SCALEKIT_INTERCEPTOR_SECRET", "")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

# Email allowlist for interceptors (comma-separated)
ALLOWED_EMAILS_RAW = os.getenv("ALLOWED_EMAILS", "")
ALLOWED_EMAILS: set[str] = {
    email.strip().lower()
    for email in ALLOWED_EMAILS_RAW.split(",")
    if email.strip()
}

# Initialize ScaleKit client for interceptor verification
scalekit_client: ScalekitClient | None = None
if SCALEKIT_ENVIRONMENT_URL and SCALEKIT_CLIENT_ID and SCALEKIT_CLIENT_SECRET:
    scalekit_client = ScalekitClient(
        SCALEKIT_ENVIRONMENT_URL,
        SCALEKIT_CLIENT_ID,
        SCALEKIT_CLIENT_SECRET,
    )


def create_auth_provider() -> ScalekitProvider | None:
    """Create ScaleKit auth provider if configured."""
    required = [SCALEKIT_ENVIRONMENT_URL, SCALEKIT_RESOURCE_ID, SERVER_URL]
    if not all(required):
        logger.warning(
            "ScaleKit OAuth not configured. Set SCALEKIT_ENVIRONMENT_URL, "
            "SCALEKIT_RESOURCE_ID, and SERVER_URL environment variables."
        )
        return None

    return ScalekitProvider(
        environment_url=SCALEKIT_ENVIRONMENT_URL,
        resource_id=SCALEKIT_RESOURCE_ID,
        base_url=SERVER_URL,
    )


def is_email_allowed(email: str) -> bool:
    """Check if an email is in the allowlist.
    
    If ALLOWED_EMAILS is not set or empty, all emails are allowed.
    """
    if not ALLOWED_EMAILS:
        return True
    return email.lower() in ALLOWED_EMAILS


def verify_interceptor_signature(request: Request, body: bytes) -> bool:
    """Verify the interceptor request signature from ScaleKit.
    
    Returns True if verification passes or if verification is not configured.
    """
    if not SCALEKIT_INTERCEPTOR_SECRET:
        logger.warning("[INTERCEPTOR] No SCALEKIT_INTERCEPTOR_SECRET configured - skipping signature verification")
        return True

    if not scalekit_client:
        logger.warning("[INTERCEPTOR] ScaleKit client not initialized - skipping signature verification")
        return True

    headers = {
        'interceptor-id': request.headers.get('interceptor-id', ''),
        'interceptor-signature': request.headers.get('interceptor-signature', ''),
        'interceptor-timestamp': request.headers.get('interceptor-timestamp', ''),
    }

    try:
        is_valid = scalekit_client.verify_interceptor_payload(
            secret=SCALEKIT_INTERCEPTOR_SECRET,
            headers=headers,
            payload=body,
        )
        if not is_valid:
            logger.warning("[INTERCEPTOR] Invalid signature")
        return is_valid
    except Exception as e:
        logger.error(f"[INTERCEPTOR] Signature verification error: {e}")
        return False


async def handle_pre_signup(request: Request) -> JSONResponse:
    """Handle ScaleKit PRE_SIGNUP interceptor.
    
    Checks if the user's email is in the allowlist before allowing signup.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature
        if not verify_interceptor_signature(request, body):
            return JSONResponse(
                {"decision": "DENY", "error": {"message": "Invalid request signature"}},
                status_code=401,
            )

        # Parse JSON body
        data = json.loads(body)

        # Extract email from interceptor context
        user_email = data.get("interceptor_context", {}).get("user_email", "")
        trigger_point = data.get("trigger_point", "")

        logger.info(f"[INTERCEPTOR] {trigger_point} for email: {user_email}")

        if is_email_allowed(user_email):
            logger.info(f"[INTERCEPTOR] ALLOW signup for: {user_email}")
            return JSONResponse({"decision": "ALLOW"})
        else:
            logger.warning(f"[INTERCEPTOR] DENY signup for: {user_email} (not in allowlist)")
            return JSONResponse({
                "decision": "DENY",
                "error": {"message": "Email not authorized for signup"}
            })

    except Exception as e:
        logger.error(f"[INTERCEPTOR] Error processing PRE_SIGNUP: {e}")
        # Fail closed - deny on error
        return JSONResponse(
            {"decision": "DENY", "error": {"message": "Internal error processing signup"}},
            status_code=500,
        )


async def handle_pre_session_creation(request: Request) -> JSONResponse:
    """Handle ScaleKit PRE_SESSION_CREATION interceptor.
    
    Checks if the user's email is in the allowlist before creating a session.
    This blocks deleted/unauthorized users even if they have a valid token.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Log the incoming request for debugging
        logger.info(f"[INTERCEPTOR] PRE_SESSION_CREATION request received")
        logger.debug(f"[INTERCEPTOR] Headers: {dict(request.headers)}")
        logger.debug(f"[INTERCEPTOR] Body (first 500 chars): {body[:500]}")

        # Verify signature
        if not verify_interceptor_signature(request, body):
            logger.warning("[INTERCEPTOR] Signature verification failed")
            return JSONResponse(
                {"decision": "DENY", "error": {"message": "Invalid request signature"}},
                status_code=401,
            )

        # Parse JSON body
        data = json.loads(body)

        # Extract email from interceptor context
        user_email = data.get("interceptor_context", {}).get("user_email", "")
        trigger_point = data.get("trigger_point", "")

        logger.info(f"[INTERCEPTOR] {trigger_point} for email: {user_email}")
        logger.debug(f"[INTERCEPTOR] Full payload: {json.dumps(data, indent=2)}")

        if is_email_allowed(user_email):
            logger.info(f"[INTERCEPTOR] ALLOW session for: {user_email}")
            response = JSONResponse({"decision": "ALLOW"})
            logger.debug(f"[INTERCEPTOR] Returning ALLOW response")
            return response
        else:
            logger.warning(f"[INTERCEPTOR] DENY session for: {user_email} (not in allowlist)")
            response = JSONResponse({
                "decision": "DENY",
                "error": {"message": "Email not authorized for access"}
            })
            logger.debug(f"[INTERCEPTOR] Returning DENY response: {response.body}")
            return response

    except Exception as e:
        logger.error(f"[INTERCEPTOR] Error processing PRE_SESSION_CREATION: {e}", exc_info=True)
        # Fail closed - deny on error
        return JSONResponse(
            {"decision": "DENY", "error": {"message": f"Internal error processing session: {str(e)}"}},
            status_code=500,
        )


async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({
        "status": "ok",
        "transport": "streamable-http",
        "oauth_provider": "scalekit" if auth_provider else "none",
    })


# Create auth provider and MCP server with auth
auth_provider = create_auth_provider()
mcp_server = create_mcp_server(auth=auth_provider)


def create_app():
    """Create ASGI app with CORS middleware and interceptor endpoints."""
    # Get the underlying Starlette app from FastMCP
    # FastMCP's ScalekitProvider automatically handles OAuth discovery endpoints
    mcp_app = mcp_server.http_app()

    # Define interceptor routes
    interceptor_routes = [
        Route("/auth/interceptors/pre-signup", handle_pre_signup, methods=["POST"]),
        Route("/auth/interceptors/pre-session-creation", handle_pre_session_creation, methods=["POST"]),
    ]

    # Create main app with interceptor routes and mount MCP app
    # IMPORTANT: Must pass mcp_app.lifespan to initialize FastMCP's session manager
    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            *interceptor_routes,
            Mount("/", app=mcp_app),  # Mount MCP app at root (FastMCP handles /mcp endpoint)
        ],
        lifespan=mcp_app.lifespan,
    )

    # Add CORS middleware for MCP Inspector and browser clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    return app


# Create the ASGI app for uvicorn
app = create_app()


def main() -> None:
    """Run MCP server with HTTP transport and ScaleKit OAuth."""
    import uvicorn

    if not auth_provider:
        logger.warning("Starting server WITHOUT OAuth authentication!")
    else:
        logger.info(f"ScaleKit environment: {SCALEKIT_ENVIRONMENT_URL}")
        logger.info(f"ScaleKit resource ID: {SCALEKIT_RESOURCE_ID}")

    if ALLOWED_EMAILS:
        logger.info(f"Email allowlist configured with {len(ALLOWED_EMAILS)} email(s)")
    else:
        logger.warning("No ALLOWED_EMAILS configured - all emails permitted")

    if not SCALEKIT_INTERCEPTOR_SECRET:
        logger.warning("No SCALEKIT_INTERCEPTOR_SECRET configured - interceptor signatures will not be verified")

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting Cin7 Core MCP Server on {host}:{port}")
    logger.info(f"Server URL: {SERVER_URL}")

    # Run with uvicorn directly using the CORS-wrapped app
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
