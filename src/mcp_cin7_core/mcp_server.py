from __future__ import annotations

import os
import logging
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("mcp_cin7_core.mcp_server")

app = FastAPI(title="mcp-cin7-core", version="0.2.0")

@app.get("/health")
async def health():
    return {"status": "ok", "transport": "streamable-http"}
