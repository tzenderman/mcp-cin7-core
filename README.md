# mcp-cin7-core

Model Context Protocol (MCP) server for Cin7 Core (DEAR) API.

## Setup

1. Create venv and install dependencies (requires `uv`):

```bash
uv venv
uv pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill credentials:

```bash
cp .env.example .env
# Edit .env to set CIN7_ACCOUNT_ID and CIN7_API_KEY
```

3. Quick import check:

```bash
uv run python -c "import mcp_cin7_core.server; print('OK')"
```

## Secrets handling

- The server expects these environment variables:
  - `CIN7_ACCOUNT_ID`, `CIN7_API_KEY` (required)
  - `CIN7_BASE_URL` (optional, defaults to https://inventory.dearsystems.com/ExternalApi/v2/)
- `.env` loading behavior:
  - On startup, the server loads `.env` from the current working directory.
  - If not found, it automatically falls back to the project root directory (the repo root containing this README).
- Recommended local setup:
  - Keep secrets only in `.env` at the project root. No need to include them in Claude’s config.
- Alternatives:
  - You can set the variables in Claude Desktop’s server `env` block, or in your OS environment. Those will be visible to the server as well.

## Run with Claude Desktop

Add an MCP server entry to your Claude Desktop config. Example:

```json
{
  "mcpServers": {
    "mcp-cin7-core": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "python", "-m", "mcp_cin7_core.server"]
    }
  }
}
```

If you prefer environment overrides instead of `.env`, you can add an `env` block:

```json
{
  "mcpServers": {
    "mcp-cin7-core": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "python", "-m", "mcp_cin7_core.server"],
      "env": {
        "CIN7_BASE_URL": "https://inventory.dearsystems.com/ExternalApi/v2/",
        "CIN7_ACCOUNT_ID": "${CIN7_ACCOUNT_ID}",
        "CIN7_API_KEY": "${CIN7_API_KEY}"
      }
    }
  }
}
```

Alternatively, if you install this package, you can use the console script:

```json
{
  "mcpServers": {
    "mcp-cin7-core": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "mcp-cin7-core"]
    }
  }
}
```

## Validate credentials

Use the `cin7_status` tool which performs a lightweight authenticated call to `GET Product` with `Page=1` and `Limit=1` to validate connectivity. See Cin7 Core Products API docs: [Products](https://dearinventory.docs.apiary.io/#reference/product).

## Next steps

- Implement: list products, get product by ID/SKU, search by name/SKU, create, and update.
- Handle pagination flags and CSV export where requested.
