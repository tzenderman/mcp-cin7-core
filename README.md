# Cin7 Core MCP Server

This is a Model Context Protocol (MCP) server implementation for [Cin7 Core](https://www.cin7.com/cin7-core/) (formerly DEAR Inventory). It provides a bridge between the MCP protocol and Cin7 Core's API, allowing for standardized access to Cin7 Core's inventory management features.

## Features

- Product management (CRUD, search, bulk snapshots for large catalogs)
- Supplier management
- Sales order management
- Purchase order management
- Stock level lookups and bulk stock snapshots
- Stock transfer lookups
- Template resources for creating and updating records
- Workflow prompts for guided product and order creation
- MCP protocol compliance

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- A [Cin7 Core](https://www.cin7.com/cin7-core/) account with API credentials

## Docs and Links

- [Cin7 Core API Documentation](https://dearinventory.docs.apiary.io/)
- [Cin7 Core Products API](https://dearinventory.docs.apiary.io/#reference/product)
- [Cin7 Core Suppliers API](https://dearinventory.docs.apiary.io/#reference/supplier)
- [Cin7 Core Sales API](https://dearinventory.docs.apiary.io/#reference/sale)
- [Cin7 Core Purchase Orders API](https://dearinventory.docs.apiary.io/#reference/purchase)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)

## Setup

### Create a Cin7 Core Account

If you don't already have a Cin7 Core account, you can sign up at [cin7.com](https://www.cin7.com/cin7-core/). You'll need API credentials to connect this server to your account.

To generate API credentials, go to **Integrations > API** in your Cin7 Core dashboard and create a new application key. You'll need:
- **Account ID** - Your Cin7 Core account identifier
- **API Key** - Your application key

### Authentication

There are 2 modes of running the Cin7 Core MCP server:

#### 1. Streamable HTTP with OAuth (Recommended for production)

This mode runs the server as a web service with OAuth 2.0 authentication via [ScaleKit](https://scalekit.com/). This is the recommended approach for shared or remote deployments, including connecting via Claude Desktop's remote MCP connector.

**Required environment variables:**
- `CIN7_ACCOUNT_ID` - Cin7 Core account identifier
- `CIN7_API_KEY` - Cin7 Core API application key
- `SCALEKIT_ENVIRONMENT_URL` - ScaleKit environment URL (e.g., `https://yourapp.scalekit.com`)
- `SCALEKIT_CLIENT_ID` - ScaleKit application client ID
- `SCALEKIT_CLIENT_SECRET` - ScaleKit application client secret
- `SCALEKIT_RESOURCE_ID` - ScaleKit resource identifier (e.g., `res_xxx`)
- `SCALEKIT_INTERCEPTOR_SECRET` - Secret for verifying interceptor payloads
- `SERVER_URL` - Your MCP server's public URL (e.g., `https://your-server.example.com`)

**Optional:**
- `ALLOWED_EMAILS` - Comma-separated list of allowed email addresses (leave empty to allow all authenticated users)
- `CIN7_BASE_URL` - Defaults to `https://inventory.dearsystems.com/ExternalApi/v2/`
- `MCP_LOG_LEVEL` - Logging level (default: INFO)
- `MCP_LOG_FILE` - Enable file logging with rotation

**Running the server:**
```bash
uv run uvicorn cin7_core_server.http_server:app --host 0.0.0.0 --port 8000
```

**Endpoints:**
- `GET /health` - Health check (no auth required)
- `GET /.well-known/oauth-protected-resource` - OAuth discovery (no auth required)
- `POST /mcp` - MCP endpoint (requires OAuth 2.0 Bearer token)

**Connecting from Claude Desktop (remote):**
1. Deploy your server (e.g., to Render)
2. Open **Claude Desktop** > **Settings** > **Connectors**
3. Click **"Add Connector"** and enter your server URL: `https://your-server.com/mcp`
4. Claude will auto-discover OAuth configuration
5. Click **"Authorize"** and log in

See [CLAUDE.md](CLAUDE.md) for detailed ScaleKit setup and interceptor configuration.

#### 2. Stdio Transport (Local development)

This mode runs the server locally using stdio transport for direct integration with Claude Desktop. No OAuth configuration needed -- Cin7 credentials are used directly.

**Required environment variables:**
- `CIN7_ACCOUNT_ID` - Cin7 Core account identifier
- `CIN7_API_KEY` - Cin7 Core API application key

**Claude Desktop configuration:**

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cin7-core": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/mcp-cin7-core",
        "run",
        "python",
        "-m",
        "cin7_core_server.stdio_server"
      ],
      "env": {
        "CIN7_ACCOUNT_ID": "your-account-id",
        "CIN7_API_KEY": "your-api-key"
      }
    }
  }
}
```

Replace `/absolute/path/to/mcp-cin7-core` with the actual path to your clone of this repository.

### Installation

```bash
# Create virtual environment and install dependencies
uv venv
uv pip install -e .

# Quick import check
uv run python -c "import cin7_core_server.mcp_server; print('OK')"
```

### Testing with MCP Inspector

```bash
# Start the HTTP server
uv run uvicorn cin7_core_server.http_server:app --host 0.0.0.0 --port 8000

# In another terminal, open MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

## Available MCP Tools

**Status & Auth:**
- `cin7_status` - Validate API credentials
- `cin7_me` - Get account/user information

**Products:**
- `cin7_products` - List products with pagination, filters, and field projection
- `cin7_get_product` - Get a single product by ID or SKU
- `cin7_create_product` - Create a new product
- `cin7_update_product` - Update an existing product

**Product Snapshots** (for large catalogs):
- `cin7_products_snapshot_start` - Start background snapshot build
- `cin7_products_snapshot_status` - Check build progress
- `cin7_products_snapshot_chunk` - Fetch paginated results
- `cin7_products_snapshot_close` - Clean up snapshot

**Suppliers:**
- `cin7_suppliers` - List suppliers with pagination
- `cin7_get_supplier` - Get a single supplier by ID or name
- `cin7_create_supplier` - Create a new supplier
- `cin7_update_supplier` - Update an existing supplier

**Sales:**
- `cin7_sales` - List sales with pagination and filters
- `cin7_get_sale` - Get a single sale
- `cin7_create_sale` - Create a new sale
- `cin7_update_sale` - Update an existing sale

**Purchase Orders:**
- `cin7_purchase_orders` - List purchase orders with pagination
- `cin7_get_purchase_order` - Get a single purchase order
- `cin7_create_purchase_order` - Create a new purchase order (always created as DRAFT)

**Stock:**
- `cin7_stock_levels` - List stock levels across all products and locations
- `cin7_get_stock` - Get stock levels for a single product
- `cin7_stock_transfers` - List stock transfers
- `cin7_get_stock_transfer` - Get a single stock transfer

**Stock Snapshots** (for large catalogs):
- `cin7_stock_snapshot_start` - Start background snapshot build
- `cin7_stock_snapshot_status` - Check build progress
- `cin7_stock_snapshot_chunk` - Fetch paginated results
- `cin7_stock_snapshot_close` - Clean up snapshot

For detailed API documentation, refer to the [MCP Protocol Specification](https://modelcontextprotocol.io/).

## For Developers

### Running Tests

```bash
# Full test suite
uv run pytest -v

# Quick pass/fail check
uv run pytest --tb=short

# Specific test file
uv run pytest tests/test_cin7_client.py -v
```

### Contributing — Test-Driven Development

This project follows a strict **test-driven development (TDD)** workflow. Every Cin7 API endpoint is implemented with proper mocks before writing any production code:

1. **Add mock data** to `tests/fixtures/` using real response shapes from the [Cin7 Core API docs](https://dearinventory.docs.apiary.io/)
2. **Write failing tests** — client tests (mock HTTP layer) and MCP tool tests (mock client layer)
3. **Implement the code** to make the tests pass

No endpoint should be merged without corresponding test coverage. See [CLAUDE.md](CLAUDE.md) for detailed test patterns and examples.

### Architecture

- **`cin7_client.py`** - Async HTTP client for Cin7 Core API
- **`mcp_server.py`** - FastMCP server with tools, resources, and prompts
- **`http_server.py`** - FastAPI wrapper with MCP Streamable HTTP transport and OAuth
- **`stdio_server.py`** - Stdio transport for local Claude Desktop integration

See [CLAUDE.md](CLAUDE.md) for comprehensive development documentation, test patterns, and architecture details.

## Security

Do not commit your `.env` file or any sensitive credentials to version control (it is included in `.gitignore` as a safe default).

## License

MIT
