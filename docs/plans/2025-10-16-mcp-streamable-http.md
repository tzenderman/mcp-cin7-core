# MCP Streamable HTTP Transport Implementation Plan

> **For Claude:** Use `${SUPERPOWERS_SKILLS_ROOT}/skills/collaboration/executing-plans/SKILL.md` to implement this plan task-by-task.

**Goal:** Convert MCP Cin7 Core server from stdio + REST to pure MCP with Streamable HTTP transport using JSON-RPC 2.0.

**Architecture:** Replace stdio MCP server and REST API with single HTTP endpoint using MCP SDK's Streamable HTTP transport. Add Resources (templates) and Prompts (workflows). Maintain Bearer token authentication. Deploy to Render.

**Tech Stack:** FastAPI, MCP Python SDK (Streamable HTTP), httpx, uvicorn

---

## 🔄 PROGRESS STATUS (Last Updated: 2025-10-16 17:30)

### ✅ Completed Tasks

**Task 1: Verify MCP SDK Support** ✅
- MCP SDK v1.13.1 fully supports Streamable HTTP
- Use `mcp_server.streamable_http_app()` method
- No additional dependencies needed
- Commit: N/A (research only)

**Task 2: Create http_server.py** ✅
- Created `src/mcp_cin7_core/http_server.py` (originally mcp_server.py) with basic FastAPI app
- Health endpoint working at `/health`
- Commit: `2ac89deaeee46ff13a2c82ee36b3de16602ca81f`

**Task 3: Add Bearer Token Auth** ✅
- Added authentication middleware to `http_server.py`
- Health check skips auth, /mcp requires Bearer token
- All tests passing (401 without token, passes with token)
- Commit: `37563e551036d3083f0362796e19d2cc1bf58126`

### ✅ Completed Tasks (continued)

**Task 4: Integrate MCP Streamable HTTP Transport** ✅
- User manually added integration to `http_server.py`
- Import: `from .mcp_server import server as mcp_server` ✅
- App creation: `mcp_app = mcp_server.streamable_http_app()` ✅
- Mount: `app.mount("/mcp", mcp_app)` ✅
- MCP endpoint tested and responding correctly

**Task 6: Add Product Template Resources** ✅
- Added blank product template resource: `cin7://templates/product`
- Added product-by-ID template: `cin7://templates/product/{product_id}`
- Added product-by-SKU template: `cin7://templates/product/sku/{sku}`
- All resources tested and verified working
- Commit: `4b4334b`

**Task 7: Add Supplier Template Resources** ✅
- Added blank supplier template: `cin7://templates/supplier`
- Added supplier-by-ID template: `cin7://templates/supplier/{supplier_id}`
- Added supplier-by-name template: `cin7://templates/supplier/name/{name}`
- All resources tested and verified working
- Commit: `6a8a12a`

**Task 8: Add Workflow Prompts** ✅
- Added `create_product` prompt - step-by-step guide for creating products
- Added `update_batch` prompt - guide for batch updates with error handling
- Added `verify_required_fields` prompt - checklist for required fields
- All prompts tested and verified working
- Commit: `4a2f4ef`

**Task 9: Remove Deprecated Template Tools** ✅
- Removed `cin7_product_template` tool (replaced by resources)
- Removed `cin7_supplier_template` tool (replaced by resources)
- 180 lines of deprecated code removed
- Verified all other tools still intact
- Commit: `7d9b746`

**Task 10: Update Render Deployment Configuration** ✅
- Updated `render.yaml` to use `http_server.py` instead of `http_app.py`
- Added `CIN7_BASE_URL` and `MCP_LOG_LEVEL` environment variables
- Verified PORT environment variable support in http_server.py
- Commit: `d59016d`

**Task 11: Remove Deprecated REST API** ✅
- Deleted `http_app.py` (465 lines)
- Deleted `openapi.json` (426 lines)
- Rewrote `CLAUDE.md` for MCP Streamable HTTP architecture
- Rewrote `README.md` with updated instructions
- ~1,000 lines of deprecated code removed
- Commit: `6e567c3`

**Task 5: Remove stdio Entry Point** ✅
- Verified no stdio entry point exists in `mcp_server.py` (already removed or never implemented)
- Confirmed `pyproject.toml` points to correct HTTP entry point: `mcp_cin7_core.http_server:main`
- Tested console script `uv run mcp-cin7-core` - works correctly
- No changes needed - task was already complete

### 📋 Pending Tasks (12-14)

- Task 12: Test Complete MCP Server Locally
- Task 13: Configure Claude Desktop Configuration
- Task 14: Final Testing & Deployment

### 📁 Current File State

**Core files (all complete):**
- `src/mcp_cin7_core/mcp_server.py` - FastMCP server with tools, resources, prompts (Tasks 6, 7, 8, 9)
- `src/mcp_cin7_core/http_server.py` - HTTP transport with auth (Tasks 2, 3, 4)
- `src/mcp_cin7_core/cin7_client.py` - Async HTTP client (unchanged)
- `render.yaml` - Deployment configuration (Task 10)
- `pyproject.toml` - Console script entry point (Task 5 verified)
- `CLAUDE.md` - MCP HTTP architecture docs (Task 11)
- `README.md` - Updated instructions (Task 11)

**Removed files:**
- `src/mcp_cin7_core/http_app.py` - Deprecated REST API (deleted in Task 11)
- `src/mcp_cin7_core/openapi.json` - REST API spec (deleted in Task 11)

### 🎯 To Resume

1. **Continue with Task 12:** Test Complete MCP Server Locally
2. **Then Task 13:** Configure Claude Desktop
3. **Finally Task 14:** Final Testing & Deployment

**Status:** Core implementation complete! Tasks 1-11 done. Ready for final testing and deployment.

### 🔍 Lessons Learned

- Haiku 4.5 struggled with Task 4 (SDK integration complexity)
- Modified wrong file (http_app.py instead of mcp_server.py)
- Consider using Sonnet 4.5 for complex SDK tasks
- Manual intervention worked - user correctly integrated MCP transport

---

## Task 1: Verify MCP SDK Support for Streamable HTTP

**Files:**
- Read: `requirements.txt`
- Read: MCP SDK documentation (via web)

**Step 1: Check current MCP SDK version**

Run: `uv pip list | grep mcp`
Expected: Shows current version of `mcp` package

**Step 2: Research Streamable HTTP support**

Search for: "MCP Python SDK StreamableHTTPTransport" or check GitHub repo
Verify: SDK has `mcp.server.streamable` or similar module for HTTP transport

**Step 3: Document findings**

Note: SDK version required, import path for transport class, any additional dependencies

---

## Task 2: Create mcp_server.py with Basic FastAPI Setup

**Files:**
- Create: `src/mcp_cin7_core/mcp_server.py`

**Step 1: Write basic FastAPI app structure**

```python
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
```

**Step 2: Test basic server starts**

Run: `uvicorn mcp_cin7_core.mcp_server:app --host 0.0.0.0 --port 8000`
Expected: Server starts, visit http://localhost:8000/health returns {"status": "ok", "transport": "streamable-http"}

**Step 3: Commit**

```bash
git add src/mcp_cin7_core/mcp_server.py
git commit -m "feat: create basic FastAPI app for MCP server"
```

---

## Task 3: Add Bearer Token Authentication Middleware

**Files:**
- Modify: `src/mcp_cin7_core/mcp_server.py`

**Step 1: Write auth middleware**

Add after imports:
```python
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
```

**Step 2: Test auth middleware**

Run server and test:
```bash
# Should succeed (health check skips auth)
curl http://localhost:8000/health

# Should fail with 401
curl -X POST http://localhost:8000/mcp

# Should succeed (with correct token)
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN"
```

Expected: Health check works without auth, /mcp requires Bearer token

**Step 3: Commit**

```bash
git add src/mcp_cin7_core/mcp_server.py
git commit -m "feat: add Bearer token authentication middleware"
```

---

## Task 4: Integrate MCP Streamable HTTP Transport

**Files:**
- Modify: `src/mcp_cin7_core/mcp_server.py`

**Step 1: Import MCP server and transport**

Add imports:
```python
from mcp.server.streamable import create_streamable_server_app
from .server import server as mcp_server
```

**Step 2: Mount MCP transport**

Replace the health endpoint section with:
```python
# Create MCP streamable HTTP app
mcp_app = create_streamable_server_app(mcp_server)

# Mount MCP endpoint
app.mount("/mcp", mcp_app)

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "transport": "streamable-http"}
```

Note: Exact import path and function name may vary based on MCP SDK version. Adjust based on Task 1 findings.

**Step 3: Test MCP endpoint responds**

Run server and test:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}}'
```

Expected: MCP protocol response (not 404/500)

**Step 4: Commit**

```bash
git add src/mcp_cin7_core/mcp_server.py
git commit -m "feat: integrate MCP Streamable HTTP transport"
```

---

## Task 5: Remove stdio Entry Point from server.py

**Files:**
- Modify: `src/mcp_cin7_core/server.py`

**Step 1: Locate and remove main() function**

Find and delete:
```python
def main():
    """Main entry point for stdio MCP server"""
    server.run()

if __name__ == "__main__":
    main()
```

**Step 2: Update console script in pyproject.toml (if exists)**

Check: `pyproject.toml` for `[project.scripts]` section
Remove or update: Any reference to `server:main`
Add new entry:
```toml
[project.scripts]
mcp-cin7-core = "mcp_cin7_core.mcp_server:main"
```

And add main function to mcp_server.py:
```python
def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
```

**Step 3: Test server still works**

Run: `uvicorn mcp_cin7_core.mcp_server:app --port 8000`
Expected: Server starts, MCP endpoint responds

**Step 4: Commit**

```bash
git add src/mcp_cin7_core/server.py pyproject.toml src/mcp_cin7_core/mcp_server.py
git commit -m "refactor: remove stdio entry point, add HTTP main"
```

---

## Task 6: Add Product Template Resources

**Files:**
- Modify: `src/mcp_cin7_core/server.py`

**Step 1: Add blank product template resource**

Add after existing @server.tool() definitions:
```python
@server.resource("cin7://templates/product")
async def resource_product_template() -> str:
    """Blank product template with all available fields and required field indicators.

    Use this template to see what fields are available when creating products.
    """
    template = {
        "SKU": "",  # REQUIRED: Unique product identifier
        "Name": "",  # REQUIRED: Product title
        "Category": "",  # REQUIRED: Product category
        "Brand": "",
        "Barcode": "",  # Typically 12-digit UPC
        "Status": "Active",  # REQUIRED: Active or Inactive
        "Type": "Stock",  # REQUIRED: Stock, Service, or Bundle
        "UOM": "Item",  # REQUIRED: Unit of measure (Item, Case, Box, etc.)
        "CostingMethod": "FIFO",  # REQUIRED: FIFO, LIFO, or Average
        "DefaultLocation": "",  # REQUIRED: Default warehouse location
        "PriceTier1": 0.0,
        "PriceTier2": 0.0,
        "PurchasePrice": 0.0,
        "COGSAccount": "5000",
        "RevenueAccount": "4000",
        "InventoryAccount": "1401",
        "PurchaseTaxRule": "Tax Exempt",
        "SaleTaxRule": "Tax Exempt",
        "Suppliers": []  # Array of supplier objects
    }
    return json.dumps(template, indent=2)
```

**Step 2: Add product-by-ID template resource**

```python
@server.resource("cin7://templates/product/{product_id}")
async def resource_product_by_id(product_id: str) -> str:
    """Get existing product as template for updates.

    Returns the current product data which can be modified and used with cin7_update_product.
    """
    client = Cin7Client.from_env()
    try:
        product = await client.get_product(product_id=product_id)
        return json.dumps(product, indent=2)
    finally:
        await client.aclose()
```

**Step 3: Add product-by-SKU template resource**

```python
@server.resource("cin7://templates/product/sku/{sku}")
async def resource_product_by_sku(sku: str) -> str:
    """Get existing product by SKU as template for updates.

    Returns the current product data which can be modified and used with cin7_update_product.
    """
    client = Cin7Client.from_env()
    try:
        product = await client.get_product(sku=sku)
        return json.dumps(product, indent=2)
    finally:
        await client.aclose()
```

**Step 4: Test resources are discoverable**

Run server and test:
```bash
# List resources
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "resources/list"}'

# Read blank template
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "cin7://templates/product"}}'
```

Expected: Resources listed, blank template returns JSON

**Step 5: Commit**

```bash
git add src/mcp_cin7_core/server.py
git commit -m "feat: add product template resources"
```

---

## Task 7: Add Supplier Template Resources

**Files:**
- Modify: `src/mcp_cin7_core/server.py`

**Step 1: Add blank supplier template resource**

```python
@server.resource("cin7://templates/supplier")
async def resource_supplier_template() -> str:
    """Blank supplier template with all available fields.

    Use this template to see what fields are available when creating suppliers.
    """
    template = {
        "Name": "",  # REQUIRED: Supplier name
        "ContactPerson": "",
        "Phone": "",
        "Email": "",
        "Website": "",
        "Address": {
            "Line1": "",
            "Line2": "",
            "City": "",
            "State": "",
            "Postcode": "",
            "Country": ""
        },
        "PaymentTerm": "",
        "Discount": 0.0,
        "TaxRule": "Tax Exempt",
        "Currency": "USD"
    }
    return json.dumps(template, indent=2)
```

**Step 2: Add supplier-by-ID template resource**

```python
@server.resource("cin7://templates/supplier/{supplier_id}")
async def resource_supplier_by_id(supplier_id: str) -> str:
    """Get existing supplier as template for updates."""
    client = Cin7Client.from_env()
    try:
        supplier = await client.get_supplier(supplier_id=supplier_id)
        return json.dumps(supplier, indent=2)
    finally:
        await client.aclose()
```

**Step 3: Add supplier-by-name template resource**

```python
@server.resource("cin7://templates/supplier/name/{name}")
async def resource_supplier_by_name(name: str) -> str:
    """Get existing supplier by name as template for updates."""
    client = Cin7Client.from_env()
    try:
        supplier = await client.get_supplier(name=name)
        return json.dumps(supplier, indent=2)
    finally:
        await client.aclose()
```

**Step 4: Test supplier resources**

Run server and test:
```bash
# Read blank supplier template
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "cin7://templates/supplier"}}'
```

Expected: Supplier template returns JSON

**Step 5: Commit**

```bash
git add src/mcp_cin7_core/server.py
git commit -m "feat: add supplier template resources"
```

---

## Task 8: Add Workflow Prompts

**Files:**
- Modify: `src/mcp_cin7_core/server.py`

**Step 1: Add create_product prompt**

```python
@server.prompt("create_product")
async def prompt_create_product() -> str:
    """Guide for creating a Cin7 Core product with all required fields."""
    return """Create a product in Cin7 Core:

1. Read cin7://templates/product to see all available fields

2. REQUIRED fields for Cin7 API:
   - SKU (unique identifier)
   - Name (product title)
   - Category (product category)
   - Status (Active or Inactive)
   - Type (Stock, Service, or Bundle)
   - UOM (Item, Case, Box, etc.)
   - CostingMethod (FIFO, LIFO, or Average)
   - DefaultLocation (warehouse location)

3. Recommended fields:
   - Brand (manufacturer name)
   - Barcode (typically 12-digit UPC)
   - PriceTier1, PriceTier2 (pricing)
   - PurchasePrice (cost)
   - Suppliers array (supplier information)

4. Accounting fields (often required):
   - COGSAccount, RevenueAccount, InventoryAccount
   - PurchaseTaxRule, SaleTaxRule

5. Use cin7_create_product tool with complete payload

6. Verify creation with cin7_get_product using returned ID
"""
```

**Step 2: Add update_batch prompt**

```python
@server.prompt("update_batch")
async def prompt_update_batch() -> str:
    """Guide for batch updating products with error collection."""
    return """Batch update products in Cin7 Core:

1. Retrieve products to update using cin7_products or snapshot tools

2. For each product, read template: cin7://templates/product/{id}

3. Prepare ALL changes (show user complete before/after list)

4. Get explicit ONE-TIME approval from user for entire batch

5. Execute updates with cin7_update_product for each product:
   - Continue on failures (don't stop)
   - Track successes and failures separately
   - Show progress: ✓ Product 1/N, ✗ Product 2/N (error), etc.

6. Report summary: X succeeded, Y failed

7. For failures, show error details and offer to retry

Error handling: Collect all errors, continue processing, report at end.
"""
```

**Step 3: Add verify_required_fields prompt**

```python
@server.prompt("verify_required_fields")
async def prompt_verify_fields() -> str:
    """Check product data completeness before creation/update."""
    return """Verify product has required Cin7 Core fields:

Required fields checklist:
□ SKU
□ Name
□ Category
□ Status
□ Type
□ UOM
□ CostingMethod
□ DefaultLocation

Recommended fields:
□ Brand
□ Barcode
□ Pricing (PriceTier1, PriceTier2, PurchasePrice)

Report any missing or empty required fields before proceeding.
"""
```

**Step 4: Test prompts are discoverable**

Run server and test:
```bash
# List prompts
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "prompts/list"}'

# Get create_product prompt
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "prompts/get", "params": {"name": "create_product"}}'
```

Expected: Prompts listed and retrievable

**Step 5: Commit**

```bash
git add src/mcp_cin7_core/server.py
git commit -m "feat: add workflow prompts for product operations"
```

---

## Task 9: Remove Deprecated Template Tools

**Files:**
- Modify: `src/mcp_cin7_core/server.py`

**Step 1: Remove cin7_product_template tool**

Find and delete the `@server.tool()` decorated function `cin7_product_template()`

**Step 2: Remove cin7_supplier_template tool**

Find and delete the `@server.tool()` decorated function `cin7_supplier_template()`

**Step 3: Test tools list**

Run server and test:
```bash
# List tools - should NOT include template tools
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

Expected: Template tools not in list (replaced by resources)

**Step 4: Commit**

```bash
git add src/mcp_cin7_core/server.py
git commit -m "refactor: remove deprecated template tools (replaced by resources)"
```

---

## Task 10: Update Render Deployment Configuration

**Files:**
- Create: `render.yaml`

**Step 1: Create render.yaml**

```yaml
services:
  - type: web
    name: mcp-cin7-core
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn mcp_cin7_core.mcp_server:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: CIN7_ACCOUNT_ID
        sync: false
      - key: CIN7_API_KEY
        sync: false
      - key: BEARER_TOKEN
        sync: false
      - key: CIN7_BASE_URL
        value: https://inventory.dearsystems.com/ExternalApi/v2/
      - key: MCP_LOG_LEVEL
        value: INFO
```

**Step 2: Verify PORT environment variable support**

Check `mcp_server.py` main function uses PORT:
```python
def main():
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**Step 3: Commit**

```bash
git add render.yaml
git commit -m "feat: add Render deployment configuration for HTTP MCP server"
```

---

## Task 11: Remove Deprecated REST API

**Files:**
- Delete: `src/mcp_cin7_core/http_app.py`

**Step 1: Remove http_app.py**

Run: `git rm src/mcp_cin7_core/http_app.py`

**Step 2: Update CLAUDE.md to remove REST API references**

Modify: `CLAUDE.md`
- Remove "HTTP REST API" from project overview
- Remove all REST endpoint documentation
- Update "Running the Server" section to only show MCP server
- Update architecture section to reflect pure MCP approach

**Step 3: Update README.md (if exists)**

Check for and update any README documentation

**Step 4: Commit**

```bash
git add CLAUDE.md README.md  # if README exists
git commit -m "refactor: remove deprecated REST API (replaced by MCP Streamable HTTP)"
```

---

## Task 12: Test Complete MCP Server Locally

**Files:**
- None (testing only)

**Step 1: Start server**

Run: `uvicorn mcp_cin7_core.mcp_server:app --host 0.0.0.0 --port 8000 --reload`

**Step 2: Test health endpoint**

Run: `curl http://localhost:8000/health`
Expected: `{"status": "ok", "transport": "streamable-http"}`

**Step 3: Test MCP initialize**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}}'
```

Expected: JSON-RPC success response with server info

**Step 4: Test tools list**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'
```

Expected: List of all tools (products, suppliers, sales, snapshots)

**Step 5: Test resources list**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "resources/list"}'
```

Expected: List of template resources

**Step 6: Test prompts list**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 4, "method": "prompts/list"}'
```

Expected: List of workflow prompts

**Step 7: Test auth rejection**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

Expected: 401 Unauthorized

**Step 8: Document test results**

Create: `docs/testing-notes.md` with results of all tests

---

## Task 13: Configure Claude Desktop to Use New MCP Server

**Files:**
- Modify: `~/.claude/config.json` (user's Claude Desktop config)

**Step 1: Update Claude Desktop configuration**

Edit Claude Desktop MCP config to use HTTP transport:
```json
{
  "mcpServers": {
    "cin7-core": {
      "url": "http://localhost:8000/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer YOUR_BEARER_TOKEN_HERE"
      }
    }
  }
}
```

**Step 2: Restart Claude Desktop**

**Step 3: Test in Claude Desktop**

- Open Claude Desktop
- Verify cin7-core server appears in MCP servers list
- Test listing tools
- Test reading a resource: "Read cin7://templates/product"
- Test calling a tool: "List 5 products from Cin7"

**Step 4: Document configuration**

Update: `CLAUDE.md` with Claude Desktop configuration instructions

**Step 5: Commit documentation**

```bash
git add CLAUDE.md
git commit -m "docs: update Claude Desktop configuration for MCP Streamable HTTP"
```

---

## Task 14: Final Testing & Deployment

**Files:**
- None (testing and deployment)

**Step 1: Run full test suite (if tests exist)**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 2: Test complete workflow in Claude Desktop**

1. Read product template
2. List products
3. Get specific product
4. Create test product (if appropriate)
5. Update test product
6. Test snapshot workflow

**Step 3: Deploy to Render**

- Push changes to main branch
- Verify Render picks up render.yaml
- Monitor deployment logs
- Test deployed endpoint

**Step 4: Test production endpoint**

```bash
curl https://your-app.onrender.com/health
curl -X POST https://your-app.onrender.com/mcp \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

Expected: Production server responds correctly

**Step 5: Update Claude Desktop to use production URL**

Change config from `http://localhost:8000/mcp` to production URL

**Step 6: Final commit**

```bash
git add .
git commit -m "chore: deployment verified, MCP Streamable HTTP migration complete"
```

---

## Notes for Implementation

**DRY Principle:**
- Reuse existing Cin7Client
- Keep all logging patterns consistent
- Don't duplicate template structures

**YAGNI Principle:**
- Only implement resources and prompts defined in design
- Don't add extra features "just in case"
- Keep snapshot system as-is (already works)

**TDD Where Applicable:**
- Protocol integration doesn't lend itself to TDD
- Integration testing via curl commands validates behavior
- Manual testing in Claude Desktop verifies end-to-end

**Commit Frequently:**
- After each working feature
- After each file removal
- After documentation updates
- Small, atomic commits with clear messages

**Testing Strategy:**
- Protocol-level: curl commands with JSON-RPC requests
- Integration: Claude Desktop connection and usage
- Deployment: Production endpoint validation
