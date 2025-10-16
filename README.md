# mcp-cin7-core

Model Context Protocol (MCP) server for Cin7 Core (DEAR) API using MCP Streamable HTTP transport.

## Features

- **MCP Streamable HTTP** - Web-based MCP transport with Bearer token authentication
- **15 Tools** - CRUD operations for products, suppliers, sales, and snapshots
- **6 Resources** - Template resources for products and suppliers
- **3 Prompts** - Workflow guides for product operations
- **Full Cin7 Core API integration** - Async HTTP client with logging and error handling

## Setup

1. Create venv and install dependencies (requires `uv`):

```bash
uv venv
uv pip install -r requirements.txt
uv pip install -e .
```

2. Copy `.env.example` to `.env` and fill credentials:

```bash
cp .env.example .env
# Edit .env to set:
# - CIN7_ACCOUNT_ID
# - CIN7_API_KEY  
# - BEARER_TOKEN (for MCP HTTP auth)
```

3. Quick import check:

```bash
uv run python -c "import mcp_cin7_core.mcp_server; print('OK')"
```

## Environment Variables

**Required:**
- `CIN7_ACCOUNT_ID` - Cin7 Core account identifier
- `CIN7_API_KEY` - Cin7 Core API application key
- `BEARER_TOKEN` - Authentication token for MCP HTTP endpoints

**Optional:**
- `CIN7_BASE_URL` - Defaults to `https://inventory.dearsystems.com/ExternalApi/v2/`
- `MCP_LOG_LEVEL` - Log level (default: INFO)
- `MCP_LOG_FILE` - Enable file logging with rotation

## Running the Server

### Local Development

```bash
uv run uvicorn mcp_cin7_core.http_server:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Render)

The server is deployed on Render and configured via `render.yaml`. Environment variables are managed in the Render dashboard.

Base URL: `https://mcp-cin7-core.onrender.com`

## Testing the Server

### Health Check

```bash
curl http://localhost:8000/health
```

### Initialize MCP Session

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}'
```

### List Tools

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'
```

## Claude Desktop Integration

Add to your Claude Desktop config (`~/.claude/config.json`):

```json
{
  "mcpServers": {
    "cin7-core": {
      "url": "http://localhost:8000/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer YOUR_BEARER_TOKEN_HERE"
      }
    }
  }
}
```

For production (Render):

```json
{
  "mcpServers": {
    "cin7-core": {
      "url": "https://mcp-cin7-core.onrender.com/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer YOUR_BEARER_TOKEN_HERE"
      }
    }
  }
}
```

## MCP Capabilities

### Tools (15)

**Status & Auth:**
- `cin7_status` - Validate credentials
- `cin7_me` - Get account information

**Products:**
- `cin7_products` - List products with pagination and filters
- `cin7_get_product` - Get single product by ID or SKU
- `cin7_create_product` - Create new product
- `cin7_update_product` - Update existing product

**Product Snapshots** (for large catalogs):
- `cin7_products_snapshot_start` - Start background build
- `cin7_products_snapshot_status` - Check build progress
- `cin7_products_snapshot_chunk` - Fetch paginated results
- `cin7_products_snapshot_close` - Clean up

**Suppliers:**
- `cin7_suppliers` - List suppliers
- `cin7_get_supplier` - Get single supplier
- `cin7_create_supplier` - Create supplier
- `cin7_update_supplier` - Update supplier

**Sales:**
- `cin7_sales` - List sales with pagination

### Resources (6)

**Product Templates:**
- `cin7://templates/product` - Blank product template
- `cin7://templates/product/{product_id}` - Existing product by ID
- `cin7://templates/product/sku/{sku}` - Existing product by SKU

**Supplier Templates:**
- `cin7://templates/supplier` - Blank supplier template
- `cin7://templates/supplier/{supplier_id}` - Existing supplier by ID
- `cin7://templates/supplier/name/{name}` - Existing supplier by name

### Prompts (3)

- `create_product` - Step-by-step guide for creating products
- `update_batch` - Batch update workflow with error handling
- `verify_required_fields` - Required fields checklist

## Architecture

- **`cin7_client.py`** - Async HTTP client for Cin7 Core API
- **`mcp_server.py`** - FastMCP server with tools, resources, and prompts
- **`http_server.py`** - FastAPI wrapper with MCP Streamable HTTP transport

See `CLAUDE.md` for detailed architecture documentation.

## Documentation

- See `CLAUDE.md` for comprehensive development documentation
- See `docs/plans/` for implementation plans and progress
- Cin7 Core API docs: https://dearinventory.docs.apiary.io/
