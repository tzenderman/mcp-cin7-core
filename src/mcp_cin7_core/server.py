from __future__ import annotations

from typing import Any, Dict
from pathlib import Path
import os
import logging
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .cin7_client import Cin7Client, Cin7ClientError


# Load environment variables from .env using a robust search strategy.
# 1) Try current working directory (default behavior)
# 2) Fallback to project root inferred from this file location
loaded = load_dotenv()
if not loaded:
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO),
                    format="%(asctime)s %(name)s %(levelname)s: %(message)s")

_log_file = os.getenv("MCP_LOG_FILE")
if _log_file:
    try:
        handler = RotatingFileHandler(_log_file, maxBytes=5_000_000, backupCount=3)
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(handler)
    except Exception:
        # If file handler fails, continue with stdout logging only
        pass

logger = logging.getLogger("mcp_cin7_core.server")

def _truncate(text: str, max_len: int = 2000) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "... [truncated]"

server = FastMCP("mcp-cin7-core")


@server.tool()
async def cin7_status() -> Dict[str, Any]:
    """Verify Cin7 Core credentials by fetching a minimal page of products."""
    logger.info("Tool call: cin7_status()")
    client = Cin7Client.from_env()
    try:
        result = await client.health_check()
        logger.info("Tool result: cin7_status() -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
async def cin7_me() -> Dict[str, Any]:
    """Call Cin7 Core Me endpoint to verify identity and account context."""
    logger.info("Tool call: cin7_me()")
    client = Cin7Client.from_env()
    try:
        result = await client.get_me()
        logger.info("Tool result: cin7_me() -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


@server.tool()
async def cin7_products(
    page: int = 1,
    limit: int = 100,
    name: str | None = None,
    sku: str | None = None,
) -> Dict[str, Any]:
    """List products with pagination and optional name/SKU filters.

    Parameters:
    - page: Page number (1-based)
    - limit: Items per page (Cin7 limits apply)
    - name: Optional name filter
    - sku: Optional SKU filter
    """
    logger.info(
        "Tool call: cin7_products(page=%s, limit=%s, name=%s, sku=%s)",
        page,
        limit,
        name,
        sku,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.list_products(page=page, limit=limit, name=name, sku=sku)
        logger.info("Tool result: cin7_products -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()


def main() -> None:
    """Entrypoint for MCP server (stdio)."""
    server.run()


if __name__ == "__main__":
    main()


