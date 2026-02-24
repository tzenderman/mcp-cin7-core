# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ScaleKit Configuration

Register your MCP server in the ScaleKit dashboard:

1. **Navigate to MCP Servers > Add MCP Server**
2. **Configure server settings:**
   - Server name: `cin7-core`
   - Resource identifier: Your server URL (e.g., `https://your-server.example.com`)
   - Scopes: `cin7:read`, `cin7:write`
3. **Enable dynamic client registration** (for MCP clients like Claude Desktop)
4. **Copy your credentials** to `.env`:
   - `SCALEKIT_ENVIRONMENT_URL`
   - `SCALEKIT_CLIENT_ID`
   - `SCALEKIT_CLIENT_SECRET`
   - `SCALEKIT_RESOURCE_ID`

See: [ScaleKit MCP Quickstart](https://docs.scalekit.com/mcp/quickstart)

### Authentication Interceptors

The server implements ScaleKit authentication interceptors to enforce an email allowlist policy. Only users with emails in the `ALLOWED_EMAILS` list can sign up or create sessions.

**Interceptor Endpoints:**
- `POST /auth/interceptors/pre-signup` - Called before a user creates a new organization
- `POST /auth/interceptors/pre-session-creation` - Called before session tokens are issued

**ScaleKit Dashboard Configuration:**

1. Navigate to **Interceptors** tab in ScaleKit dashboard
2. Create two interceptors:

   **Pre-Signup Interceptor:**
   - Name: `Email Allowlist - Pre-Signup`
   - Trigger point: `PRE_SIGNUP`
   - Endpoint: `https://your-server.com/auth/interceptors/pre-signup`
   - Timeout: 5 seconds
   - Fallback: Fail closed (deny if timeout)

   **Pre-Session Creation Interceptor:**
   - Name: `Email Allowlist - Pre-Session`
   - Trigger point: `PRE_SESSION_CREATION`
   - Endpoint: `https://your-server.com/auth/interceptors/pre-session-create`
   - Timeout: 5 seconds
   - Fallback: Fail closed (deny if timeout)

3. Copy the **Interceptor Secret** from the dashboard and set it as `SCALEKIT_INTERCEPTOR_SECRET` in your `.env`
4. Enable both interceptors

**Email Allowlist:**

Set `ALLOWED_EMAILS` in your `.env` file with a comma-separated list of authorized emails:

```bash
ALLOWED_EMAILS=alice@example.com,bob@example.com,admin@company.org
```

If `ALLOWED_EMAILS` is empty or not set, all authenticated users are allowed.

## Testing

### Running Tests

```bash
# Full test suite
uv run pytest -v

# Quick pass/fail check
uv run pytest --tb=short

# Specific test file
uv run pytest tests/test_cin7_client.py -v

# Specific test class or method
uv run pytest tests/test_cin7_client.py::TestGetProduct -v
uv run pytest tests/test_cin7_client.py::TestGetProduct::test_returns_product_by_sku -v
```

### Test Structure

```
tests/
  conftest.py                  # Shared fixtures (mock_client, mock_cin7_class, mock_response)
  fixtures/                    # Centralized mock API responses
    __init__.py
    common.py                  # Me, health check, error responses
    products.py                # Product API responses
    suppliers.py               # Supplier API responses
    sales.py                   # Sale API responses
    purchase_orders.py         # Purchase order API responses
    stock.py                   # Stock availability responses
    stock_transfers.py         # Stock transfer API responses
  test_cin7_client.py          # Client method tests (HTTP mocking)
  test_mcp_server.py           # MCP tool tests (client mocking)
  test_mcp_resources.py        # MCP resource handler tests
  test_mcp_prompts.py          # MCP prompt function tests
  test_mcp_snapshots.py        # Product + stock snapshot lifecycle tests
  test_http_server.py          # HTTP server (server_http.py) endpoint tests
```

### Test-Driven Development Workflow

When adding a new Cin7 API endpoint, follow this order:

1. **Read the API docs** at https://dearinventory.docs.apiary.io/ for the endpoint:
   - Exact HTTP method (`GET`, `POST`, `PUT`)
   - Exact API path string (e.g., `saleList` not `SaleList`, `product-suppliers` not `ProductSuppliers`)
   - Every query parameter name exactly as shown (e.g., `Sku` not `SKU`, `ID` not `ProductID`)
   - Default values for pagination params (typically `Page=1`, `Limit=100`)
   - Required fields for request bodies
2. **Add mock data** to `tests/fixtures/` for the new endpoint's API responses
3. **Write request parameter contract tests** in `TestApiRequestContracts` in `test_cin7_client.py` (these will fail until step 6):
   - Assert the exact HTTP method
   - Assert the exact API path string — pulled directly from the API docs URL
   - Assert each query parameter name and type — pulled directly from the API docs parameter list
   - Assert default values (Page, Limit) match the API docs defaults
   - Assert wrong/legacy param names are NOT sent (e.g., `assert "SKU" not in params`)
4. **Write client response/error tests** in `test_cin7_client.py`:
   - Verify response parsing and error handling
5. **Write MCP tool tests** in `test_mcp_server.py`:
   - Mock the client layer (`mock_instance.method = AsyncMock(...)`)
   - Verify correct client method called with right args
   - Verify field projection applied (if applicable)
6. **Implement the client method** in `cin7_client.py` — tests from step 3 now pass
7. **Implement the MCP tool** in the appropriate `resources/*.py` module
8. **Run `uv run pytest`** to verify all tests pass
9. **Add resource/prompt tests** if the endpoint has templates or workflow guides

### Test Patterns

**Request parameter contract test** (assert exact method, path, param names from API docs):
```python
# In TestApiRequestContracts in test_cin7_client.py
async def test_list_products_sku_filter_uses_sku_not_uppercase(self, mock_client):
    """API docs: GET /Product?Sku=... — param is 'Sku' (not 'SKU').

    See: https://dearinventory.docs.apiary.io/#reference/product/product/get
    """
    mock_client._request = AsyncMock(return_value=self._ok_resp(PRODUCT_LIST_RESPONSE))

    await mock_client.list_products(sku="TEST-001")

    call = mock_client._request.call_args
    assert call[0][0] == "get"
    assert call[0][1] == "Product"
    params = call.kwargs.get("params", {})
    assert "Sku" in params, "API param is 'Sku' (not 'SKU')"
    assert "SKU" not in params
```

**Client response/filter test** (mock `_request`, verify params/responses/errors):
```python
async def test_list_products_with_name_filter(self, mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = PRODUCT_LIST_RESPONSE
    mock_client._request = AsyncMock(return_value=mock_resp)

    result = await mock_client.list_products(name="Widget")

    call_args = mock_client._request.call_args
    params = call_args.kwargs.get("params", {})
    assert params["Name"] == "Widget"
    assert "Products" in result
```

**MCP tool test** (mock client, verify delegation/projection):
```python
async def test_cin7_products_default_projection(self, mock_cin7_class):
    mock_class, mock_instance = mock_cin7_class
    mock_instance.list_products = AsyncMock(return_value=PRODUCT_LIST_RESPONSE)

    from cin7_core_server.resources.products import cin7_products
    result = await cin7_products()

    item = result["Products"][0]
    assert "SKU" in item
    assert "Name" in item
    assert "Brand" not in item  # Excluded by default projection
```

### Contract Tests (API Shape Documentation)

Every client method must have contract tests that verify the exact API request it sends. There are two kinds, both derived directly from the API docs at https://dearinventory.docs.apiary.io/:

---

#### 1. Request Parameter Contract Tests (`TestApiRequestContracts` in `test_cin7_client.py`)

Every GET/list/get-single method must have tests in `TestApiRequestContracts` that assert:

- **HTTP method** — `call[0][0] == "get"`
- **Exact API path** — pulled from the API docs URL (e.g., `"saleList"` not `"SaleList"`, `"product-suppliers"` not `"ProductSuppliers"`)
- **Exact query parameter names** — pulled from the API docs parameter list (e.g., `"Sku"` not `"SKU"`, `"ID"` not `"ProductID"`)
- **Default pagination values** — `Page=1`, `Limit=100` where the API docs show these defaults
- **Absence of wrong names** — `assert "SKU" not in params` when the correct name is `"Sku"`

Each test must reference the API docs URL in its docstring. Example:

```python
async def test_list_sales_path_is_salelist_lowercase_l(self, mock_client):
    """API docs: GET /saleList (lowercase 'l') — not 'SaleList'.

    See: https://dearinventory.docs.apiary.io/#reference/sale/salelist/get
    """
    mock_client._request = AsyncMock(return_value=self._ok_resp(SALE_LIST_RESPONSE))
    await mock_client.list_sales()
    call = mock_client._request.call_args
    assert call[0][0] == "get"
    assert call[0][1] == "saleList", "API path is 'saleList' (lowercase 'l'), not 'SaleList'"
```

**Confirmed API paths and parameter names (from API docs):**

| Client method | HTTP | Path | Key params |
|---|---|---|---|
| `get_me` | GET | `me` | — |
| `list_products` | GET | `Product` | `Page`, `Limit`, `Sku` (not `SKU`), `Name` |
| `get_product` | GET | `Product` | `ID`, `Sku` (not `SKU`) |
| `list_suppliers` | GET | `Supplier` | `Page`, `Limit`, `ID`, `Name` |
| `get_supplier` | GET | `Supplier` | `ID`, `Name` |
| `list_sales` | GET | `saleList` | `Page`, `Limit`, `Search` |
| `get_sale` | GET | `Sale` | `ID` |
| `list_purchase_orders` | GET | `purchaseList` | `Page`, `Limit`, `Search` |
| `get_purchase_order` | GET | `Purchase` | `ID` |
| `list_stock_transfers` | GET | `stockTransferList` | `Page`, `Limit`, `Status`, `Search` |
| `get_stock_transfer` | GET | `stockTransfer` | `TaskID` |
| `list_product_availability` | GET | `ref/productavailability` | `Page`, `Limit`, `ID`, `Sku`, `Location`, `Batch`, `Category` |
| `get_product_suppliers` | GET | `product-suppliers` | `ProductID` |
| `update_product_suppliers` | PUT | `product-suppliers` | — |

---

#### 2. Request Body Contract Tests (`test_mcp_server.py`)

Create endpoints have **contract tests** in `tests/test_mcp_server.py` that document the expected request body shape. These tests:

- Use **complete, API-accurate payloads** matching the [Cin7 Core API Blueprint](https://dearinventory.docs.apiary.io/api-description-document)
- Assert the payload is forwarded unchanged to the Cin7 client (`assert_called_once_with(payload)`)
- Have docstrings listing required fields and linking to the API docs

**Required fields by endpoint (per API docs):**

| Endpoint | Required fields |
|---|---|
| `cin7_create_product` | `SKU`, `Name`, `Category`, `Type`, `CostingMethod`, `UOM`, `Status` |
| `cin7_create_supplier` | `Name`, `Currency`, `PaymentTerm`, `AccountPayable`, `TaxRule` |
| `cin7_create_sale` | `Customer` (or `CustomerID`), `Location`, `Status`, `SkipQuote` |
| `cin7_create_purchase_order` | `Supplier` (or `SupplierID`), `Location`, `Status`, `OrderDate` |

**Line item shape** (for `Lines` array in Sale and Purchase Order):

| Field | Type | Notes |
|---|---|---|
| `ProductID` | Guid | From `cin7_get_product` |
| `SKU` | String | Product SKU |
| `Name` | String | Product name |
| `Quantity` | Decimal | Minimum 1 |
| `Price` | Decimal | Unit price |
| `Tax` | Decimal | Tax amount |
| `TaxRule` | String | Tax rule name |
| `Total` | Decimal | `Price × Quantity − Discount + Tax` |

**Note:** `Lines` are NOT required by the Cin7 API for creating a Sale or Purchase header. They are forwarded internally via a second API call (`POST /sale/order` or `POST /purchase/order`). The two-step process is tested in `test_cin7_client.py`.

When adding a new create endpoint, add a contract test named `test_create_<resource>_api_contract` with:
1. A docstring listing required fields and the API docs URL
2. A complete payload with all required fields
3. `assert_called_once_with(payload)` to verify passthrough

### Mock Data Fixtures

All mock data lives in `tests/fixtures/` modules. Each module exports constants representing realistic API responses. Import them in tests:

```python
from tests.fixtures.products import PRODUCT_LIST_RESPONSE, PRODUCT_SINGLE
from tests.fixtures.suppliers import SUPPLIER_SINGLE
```

To add new fixtures: create constants in the appropriate module following the existing naming pattern (`<ENTITY>_<VARIANT>`).

## Architecture

### Core Components

**`cin7_core_server/cin7_client.py`** - Async HTTP client for Cin7 Core API
- Per-request `httpx.AsyncClient` pattern (no persistent connection)
- Exponential backoff retry on 429/5xx errors and network/timeout failures (3 attempts)
- Automatic request/response logging with header redaction
- Built-in error handling with `Cin7ClientError`
- Created via `Cin7Client.from_env()` which reads environment variables

**`cin7_core_server/server.py`** - Slim MCP server registration
- Imports tool/resource/prompt functions from `resources/` modules
- Registers everything with FastMCP via `create_mcp_server()`
- Tools follow naming convention: `cin7_<resource>` (e.g., `cin7_products`, `cin7_get_product`)

**`cin7_core_server/resources/`** - Modular tool implementations
- `auth.py` - `cin7_status`, `cin7_me`
- `products.py` - CRUD for products with field projection
- `suppliers.py` - CRUD for suppliers
- `sales.py` - Sales list/get/create/update (two-step API)
- `purchase_orders.py` - PO list/get/create (two-step API)
- `stock.py` - Stock levels, get_stock, stock transfers
- `snapshots.py` - Product + stock snapshot build/status/chunk/close
- `templates.py` - Resource handlers for templates (product, supplier, PO, sale)
- `prompts.py` - Workflow prompts (create_product, update_batch, etc.)

**`cin7_core_server/utils/`** - Shared utilities
- `projection.py` - Field projection helpers (`project_items`, `project_stock_items`)
- `logging.py` - Logging setup and `truncate` helper

**`cin7_core_server/server_http.py`** - Starlette HTTP wrapper for MCP Streamable HTTP transport
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

### Stock Availability Response Fields

| Field | Type | Description |
|-------|------|-------------|
| SKU | string | Product identifier |
| Location | string | Warehouse name |
| OnHand | decimal | Physical stock quantity |
| Available | decimal | OnHand - Allocated |
| Allocated | decimal | Reserved for pending orders |
| OnOrder | decimal | On purchase orders, not received |
| InTransit | decimal | Being transferred |
| NextDeliveryDate | datetime | Expected delivery |
| Bin | string | Bin location |
| Batch | string | Batch/lot number |

### API Integration Pattern

All tools follow this pattern (no cleanup needed - per-request client):
```python
client = Cin7Client.from_env()
result = await client.<operation>()
return result
```

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

### Checking stock levels

Single product lookup:
```python
# Get stock for a single SKU across all locations
result = await cin7_get_stock(sku="PRODUCT-SKU")
# Returns: sku, locations[], total_on_hand, total_available
```

### Syncing stock with external systems

For large catalogs, use the snapshot workflow:

1. Start: `cin7_stock_snapshot_start(fields=["Allocated", "OnOrder"])`
2. Poll status: `cin7_stock_snapshot_status(snapshot_id="...")`
3. Fetch chunks: `cin7_stock_snapshot_chunk(snapshot_id="...", offset=0, limit=500)`
4. Continue fetching with `nextOffset` until `null`
5. Clean up: `cin7_stock_snapshot_close(snapshot_id="...")`

### Creating a purchase order

1. Read template: `cin7://templates/purchase_order` resource
2. Get supplier info: `cin7_get_supplier(name="Supplier Name")` or by ID
3. Get product info for line items: `cin7_get_product(sku="PRODUCT-SKU")` to retrieve ProductID, SKU, and Name
4. Fill required PO-level fields:
   - `Supplier` (supplier name or ID)
   - `Location` (warehouse location)
   - `OrderDate` (YYYY-MM-DD format)
   - `Lines` (array of line items)
5. Fill required fields for each line item:
   - `ProductID` (GUID from cin7_get_product)
   - `SKU` (product SKU)
   - `Name` (product name)
   - `Quantity` (order quantity, minimum 1)
   - `Price` (unit price)
   - `Tax` (tax amount)
   - `TaxRule` (tax rule name, e.g., "Tax Exempt")
   - `Total` (line total for validation: (Price x Quantity) - Discount + Tax)
6. Create: `cin7_create_purchase_order(payload)`
7. **Important**: All POs are automatically created with `Status="DRAFT"` to allow review before authorization
8. User reviews and authorizes the PO in Cin7 Core web interface
9. Use `create_purchase_order` prompt for step-by-step guidance

## Development Notes

- Per-request `httpx.AsyncClient` with automatic retry (no manual cleanup needed)
- Rate limit info available in response headers: `X-RateLimit-Remaining`
- Product and supplier IDs have different types (int vs string) - respect API schema
- Field projection reduces data transfer and improves performance for large datasets
- Snapshot system prevents memory exhaustion on large catalogs
- All authentication credentials are redacted in logs for security
- MCP Streamable HTTP transport supports both batch and streaming response modes
- Resources replace the old template tools - use `resources/read` instead
