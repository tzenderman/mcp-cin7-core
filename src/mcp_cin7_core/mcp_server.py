from __future__ import annotations

import os
import logging
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("mcp_cin7_core.mcp_server")

app = FastAPI(title="mcp-cin7-core", version="0.2.0")

BEARER_TOKEN = os.getenv("BEARER_TOKEN")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth for health check
    if request.url.path == "/health":
        return await call_next(request)

    # Require auth for /mcp endpoints
    if request.url.path.startswith("/mcp"):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()

        if not BEARER_TOKEN:
            logger.error("BEARER_TOKEN not configured")
            return Response(status_code=500, content="Server misconfigured")

        if token != BEARER_TOKEN:
            logger.warning(f"Invalid token attempt from {request.client.host}")
            return Response(status_code=401, content="Unauthorized")

    return await call_next(request)

@app.get("/health")
async def health():
    return {"status": "ok", "transport": "streamable-http"}
