"""Stdio transport server for local Claude Desktop testing.

This module provides a minimal wrapper around the existing FastMCP server
to enable stdio transport for local development with Claude Desktop.

Usage:
    python -m cin7_core_server.stdio_server

Environment Variables (required):
    CIN7_ACCOUNT_ID - Cin7 Core account identifier
    CIN7_API_KEY - Cin7 Core API key

Environment Variables (optional):
    MCP_LOG_LEVEL - Logging level (default: INFO)
    MCP_LOG_FILE - Log file path with rotation
    CIN7_BASE_URL - API base URL (defaults to production)
"""

from .server import server


def main():
    """Run the MCP server using stdio transport for Claude Desktop.

    This reuses the existing FastMCP server instance from server.py,
    ensuring identical behavior across HTTP and stdio transports.

    No OAuth authentication is required for stdio - the server relies on
    Cin7 credentials (CIN7_ACCOUNT_ID and CIN7_API_KEY) from environment.
    """
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
