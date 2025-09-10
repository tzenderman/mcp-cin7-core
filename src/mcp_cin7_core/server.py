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


@server.tool()
async def cin7_get_product(
    product_id: int | None = None,
    sku: str | None = None,
) -> Dict[str, Any]:
    """Get a single product by ID or SKU.

    Returns the first matching product object.
    """
    logger.info(
        "Tool call: cin7_get_product(product_id=%s, sku=%s)",
        product_id,
        sku,
    )
    client = Cin7Client.from_env()
    try:
        result = await client.get_product(product_id=product_id, sku=sku)
        logger.info("Tool result: cin7_get_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

@server.tool()
async def cin7_update_product(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Cin7 Core product via PUT Product.

    Provide the JSON payload as defined by Cin7 Core API. This tool forwards
    the payload to PUT Product and returns the API response.

    Docs: https://dearinventory.docs.apiary.io/#reference/product
    """
    logger.info("Tool call: cin7_update_product(payload=%s)", _truncate(str(payload)))
    client = Cin7Client.from_env()
    try:
        result = await client.update_product(payload)
        logger.info("Tool result: cin7_update_product -> %s", _truncate(str(result)))
        return result
    finally:
        await client.aclose()

@server.tool()
async def cin7_product_template(
    product_id: int | None = None,
    sku: str | None = None,
    include_defaults: bool = True,
) -> Dict[str, Any]:
    """Return a Cin7 Core Product payload template.

    - If `product_id` or `sku` is provided, fetch that product and return an
      editable template preserving field structure (helpful for PUT updates).
    - Otherwise, return a broad template with common fields and placeholders.
    """
    logger.info(
        "Tool call: cin7_product_template(product_id=%s, sku=%s, include_defaults=%s)",
        product_id,
        sku,
        include_defaults,
    )

    if product_id is not None or sku is not None:
        client = Cin7Client.from_env()
        try:
            product = await client.get_product(product_id=product_id, sku=sku)
            # Return a shallow copy so callers can edit safely.
            logger.info(
                "Tool result: cin7_product_template (from existing) -> %s",
                _truncate(str(product)),
            )
            return dict(product) if isinstance(product, dict) else {"result": product}
        finally:
            await client.aclose()

    template: Dict[str, Any] = {
        # Identity
        "ID": 0,
        "SKU": "",
        "Name": "",
        # Classification
        "Category": "",
        "Brand": "",
        "Type": "Stock",
        "CostingMethod": "FIFO",
        # Stock & dimensions
        "Length": 0.0,
        "Width": 0.0,
        "Height": 0.0,
        "Weight": 0.0,
        "UOM": "Item",
        # Visibility & status
        "Status": "Active",
        # Descriptions
        "Description": "",
        "ShortDescription": "",
        # Codes
        "Barcode": "",
        "HSCode": "",
        "CountryOfOrigin": "",
        # Reordering
        "MinimumBeforeReorder": None,
        "ReorderQuantity": None,
        # Pricing examples (expand tiers as needed)
        "PriceTier1": None,
        "PurchasePrice": None,
        # Tax
        "TaxRules": {
            "PurchaseTaxRule": "",
            "SaleTaxRule": "",
        },
        # Misc
        "InternalNote": "",
        "ProductTags": [],
        "AdditionalAttributes": {},
        # Media (example structure if supported)
        "Images": [],
    }
    if not include_defaults:
        # Remove defaulted numeric/enum fields if caller prefers sparse output
        for key in [
            "Type",
            "CostingMethod",
            "UOM",
            "Status",
            "Length",
            "Width",
            "Height",
            "Weight",
        ]:
            template.pop(key, None)

    logger.info("Tool result: cin7_product_template -> %s", _truncate(str(template)))
    return template

def main() -> None:
    """Entrypoint for MCP server (stdio)."""
    server.run()


if __name__ == "__main__":
    main()


