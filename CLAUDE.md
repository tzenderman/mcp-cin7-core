# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides access to the Cin7 Core (DEAR) inventory management API. The server uses **MCP Streamable HTTP transport** for web-based communication.

The project wraps the Cin7 Core API to enable AI-powered inventory management operations including products, suppliers, and sales management.

## Development Setup

### Initial Setup

```bash
# Create virtual environment and install dependencies (requires uv)
uv venv
uv pip install -r requirements.txt

# Install package in editable mode for development
uv pip install -e .
```

### Environment Configuration

Copy `.env.example` to `.env` and configure:
- `CIN7_ACCOUNT_ID` - Cin7 Core account identifier
- `CIN7_API_KEY` - Cin7 Core API application key
- `BEARER_TOKEN` - Authentication token for MCP HTTP endpoints
- `CIN7_BASE_URL` - (Optional) Defaults to `https://inventory.dearsystems.com/ExternalApi/v2/`
- `MCP_LOG_LEVEL` - (Optional) Logging level (default: INFO)

The server automatically searches for `.env` in the current directory, falling back to the project root if not found.

### Validation

```bash
# Quick import check
uv run python -c "import mcp_cin7_core.mcp_server; print('OK')"
```

## Running the Server

### MCP HTTP Server (for web access and Claude Desktop)

```bash
# Using uvicorn
uv run uvicorn mcp_cin7_core.http_server:app --host 0.0.0.0 --port 8000 --reload

# Using the main entrypoint
uv run python -m mcp_cin7_core.http_server
```

The server provides:
- **Health endpoint**: `GET /health` (no auth required)
- **MCP endpoint**: `/mcp` (requires Bearer token auth)
  - Supports both batch (JSON) and streaming (SSE) responses
  - Built-in session management
  - Full MCP protocol support (tools, resources, prompts)

### Testing MCP endpoints

```bash
# Test health (no auth)
curl http://localhost:8000/health

# Initialize MCP session
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}'
```

## Architecture

### Core Components

**`src/mcp_cin7_core/cin7_client.py`** - Async HTTP client for Cin7 Core API
- Uses `httpx.AsyncClient` for all API communication
- Automatic request/response logging with header redaction
- Built-in error handling with `Cin7ClientError`
- Created via `Cin7Client.from_env()` which reads environment variables
- Always call `await client.aclose()` after use to clean up connections

**`src/mcp_cin7_core/mcp_server.py`** - MCP server implementation using FastMCP
- Exposes MCP tools for Cin7 Core operations (products, suppliers, sales)
- Provides MCP resources for templates (products, suppliers)
- Provides MCP prompts for workflow guidance
- Tools follow naming convention: `cin7_<resource>` (e.g., `cin7_products`, `cin7_get_product`)
- Implements product snapshot system for handling large datasets (see Snapshot System below)
- All tool calls log entry/exit with truncated payloads for debugging

**`src/mcp_cin7_core/http_server.py`** - FastAPI HTTP wrapper for MCP Streamable HTTP transport
- Mounts the FastMCP server at `/mcp` endpoint
- Provides Bearer token authentication middleware
- Health check endpoint at `/health`
- Supports MCP session management via SDK
- Entry point: `main()` function runs the HTTP server

### Product Snapshot System

For handling large product datasets without overwhelming API rate limits or memory:

1. **Start snapshot**: `cin7_products_snapshot_start()` creates a background task
2. **Check status**: `cin7_products_snapshot_status()` returns build progress
3. **Fetch chunks**: `cin7_products_snapshot_chunk()` retrieves paginated results
4. **Close**: `cin7_products_snapshot_close()` cleans up and cancels if still running

Snapshots:
- Auto-expire after 15 minutes (`SNAPSHOT_TTL_SECONDS`)
- Capped at 250k items (`SNAPSHOT_MAX_ITEMS`)
- Support field projection to limit data transfer
- Stored in-memory in `_snapshots` dict with UUID keys

### API Integration Pattern

All tools follow this pattern:
```python
client = Cin7Client.from_env()
try:
    result = await client.<operation>()
    return result
finally:
    await client.aclose()
```

### Resource System

Products and suppliers have MCP resources for templates:

**Product Resources:**
- `cin7://templates/product` - Blank product template with all fields
- `cin7://templates/product/{product_id}` - Existing product as template
- `cin7://templates/product/sku/{sku}` - Product by SKU as template

**Supplier Resources:**
- `cin7://templates/supplier` - Blank supplier template with all fields
- `cin7://templates/supplier/{supplier_id}` - Existing supplier as template
- `cin7://templates/supplier/name/{name}` - Supplier by name as template

Resources are read via MCP `resources/read` method and return JSON data suitable for create/update operations.

### Prompt System

Workflow guidance prompts:
- `create_product` - Step-by-step guide for creating Cin7 products with all required fields
- `update_batch` - Guide for batch updating products with proper error handling
- `verify_required_fields` - Checklist to verify product data completeness before submission

Prompts are retrieved via MCP `prompts/get` method.

### Logging

Comprehensive logging throughout:
- `MCP_LOG_LEVEL` environment variable controls log level (default: INFO)
- `MCP_LOG_FILE` enables file logging with rotation (5MB max, 3 backups)
- HTTP client logs all requests/responses with timing
- Sensitive headers (auth tokens) are automatically redacted
- MCP server logs all tool/resource calls with truncated output

## Common Operations

### Creating a product

1. Read template: `cin7://templates/product` resource
2. Fill required fields: `SKU`, `Name`, `Category`, `Status`, `Type`, `UOM`, `CostingMethod`, `DefaultLocation`
3. Create: `cin7_create_product(payload)`
4. Use `create_product` prompt for step-by-step guidance

### Updating a product

1. Read existing as template: `cin7://templates/product/{id}` or `cin7://templates/product/sku/{sku}`
2. Modify fields in the returned template
3. Update: `cin7_update_product(payload)`

### Batch updating products

1. Use `update_batch` prompt for workflow guidance
2. Retrieve products to update
3. Read templates for each product
4. Prepare all changes and get user approval
5. Execute updates with error collection
6. Report summary of successes and failures

### Listing products with projection

By default, `cin7_products()` returns only `SKU` and `Name` to reduce data transfer. Use the `fields` parameter to request additional fields:

```python
# Get SKU, Name, and Price
cin7_products(fields=["PriceTier1", "PurchasePrice"])
```

### Working with large product catalogs

Use the snapshot workflow for catalogs with thousands of products:

1. Start: `cin7_products_snapshot_start(page=1, limit=100, fields=["Category"])`
2. Poll status: `cin7_products_snapshot_status(snapshot_id="...")`
3. Fetch chunks: `cin7_products_snapshot_chunk(snapshot_id="...", offset=0, limit=100)`
4. Continue fetching with `nextOffset` until `null`
5. Clean up: `cin7_products_snapshot_close(snapshot_id="...")`

## MCP Protocol Reference

### Available MCP Tools

**Status & Auth:**
- `cin7_status()` - Validate credentials with lightweight API call
- `cin7_me()` - Get account/user information

**Products:**
- `cin7_products(page, limit, name, sku, fields)` - List with pagination and filters
- `cin7_get_product(product_id, sku)` - Get single product
- `cin7_create_product(payload)` - Create new product
- `cin7_update_product(payload)` - Update existing product

**Product Snapshots:**
- `cin7_products_snapshot_start(page, limit, name, sku, fields)` - Start background build
- `cin7_products_snapshot_status(snapshot_id)` - Check build progress
- `cin7_products_snapshot_chunk(snapshot_id, offset, limit)` - Fetch chunk
- `cin7_products_snapshot_close(snapshot_id)` - Clean up

**Suppliers:**
- `cin7_suppliers(page, limit, name)` - List with pagination
- `cin7_get_supplier(supplier_id, name)` - Get single supplier
- `cin7_create_supplier(payload)` - Create new supplier
- `cin7_update_supplier(payload)` - Update existing supplier

**Sales:**
- `cin7_sales(page, limit, search, fields)` - List sales (returns Order, SaleOrderNumber, Customer, Location by default)

### Available MCP Resources

**Product Templates:**
- `cin7://templates/product` - Blank product template
- `cin7://templates/product/{product_id}` - Existing product by ID
- `cin7://templates/product/sku/{sku}` - Existing product by SKU

**Supplier Templates:**
- `cin7://templates/supplier` - Blank supplier template
- `cin7://templates/supplier/{supplier_id}` - Existing supplier by ID
- `cin7://templates/supplier/name/{name}` - Existing supplier by name

### Available MCP Prompts

- `create_product` - Product creation workflow guide
- `update_batch` - Batch update workflow guide  
- `verify_required_fields` - Required fields checklist

## Cin7 Core API Reference

- Base URL: https://inventory.dearsystems.com/ExternalApi/v2/
- Products: https://dearinventory.docs.apiary.io/#reference/product
- Suppliers: https://dearinventory.docs.apiary.io/#reference/supplier
- Sales: https://dearinventory.docs.apiary.io/#reference/sale

## Development Notes

- All async operations use `httpx.AsyncClient` - ensure proper cleanup with `aclose()`
- Rate limit info available in response headers: `X-RateLimit-Remaining`
- Product and supplier IDs have different types (int vs string) - respect API schema
- Field projection reduces data transfer and improves performance for large datasets
- Snapshot system prevents memory exhaustion on large catalogs
- All authentication credentials are redacted in logs for security
- MCP Streamable HTTP transport supports both batch and streaming response modes
- Resources replace the old template tools - use `resources/read` instead
