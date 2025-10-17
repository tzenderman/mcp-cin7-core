from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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

BEARER_TOKEN = os.getenv("BEARER_TOKEN")

@app.get("/health")
async def health():
    return {"status": "ok", "transport": "streamable-http"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth for health check and CORS preflight
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)

    # Require auth for /mcp endpoints
    if request.url.path.startswith("/mcp"):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()

        if not BEARER_TOKEN:
            logger.error("BEARER_TOKEN not configured")
            return Response(status_code=500, content="Server misconfigured")

        # Debug logging
        logger.debug(f"Auth header received: {auth_header!r}")
        logger.debug(f"Extracted token: {token!r}")
        logger.debug(f"Expected token: {BEARER_TOKEN!r}")
        logger.debug(f"Tokens match: {token == BEARER_TOKEN}")

        if token != BEARER_TOKEN:
            logger.warning(f"Invalid token attempt from {request.client.host}")
            return Response(status_code=401, content="Unauthorized")

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
