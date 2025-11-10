# Stdio Transport Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add stdio transport support to enable local testing with Claude Desktop without affecting the HTTP server.

**Architecture:** Create minimal stdio_server.py that imports and runs the existing FastMCP server with stdio transport. No code duplication, zero impact on http_server.py.

**Tech Stack:** FastMCP (already includes stdio support), Python 3.10+

---

## Task 1: Create stdio server module

**Files:**
- Create: `src/mcp_cin7_core/stdio_server.py`

**Step 1: Write the stdio server module**

Create `src/mcp_cin7_core/stdio_server.py`:

```python
"""Stdio transport server for local Claude Desktop testing.

This module provides a minimal wrapper around the existing FastMCP server
to enable stdio transport for local development with Claude Desktop.

Usage:
    python -m mcp_cin7_core.stdio_server

Environment Variables (required):
    CIN7_ACCOUNT_ID - Cin7 Core account identifier
    CIN7_API_KEY - Cin7 Core API key

Environment Variables (optional):
    MCP_LOG_LEVEL - Logging level (default: INFO)
    MCP_LOG_FILE - Log file path with rotation
    CIN7_BASE_URL - API base URL (defaults to production)
"""

from .mcp_server import server


def main():
    """Run the MCP server using stdio transport for Claude Desktop.

    This reuses the existing FastMCP server instance from mcp_server.py,
    ensuring identical behavior across HTTP and stdio transports.

    No OAuth authentication is required for stdio - the server relies on
    Cin7 credentials (CIN7_ACCOUNT_ID and CIN7_API_KEY) from environment.
    """
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
```

**Step 2: Verify the module can be imported**

Run: `uv run python -c "from mcp_cin7_core import stdio_server; print('✓ Import successful')"`

Expected: `✓ Import successful` with debug logs

**Step 3: Commit the stdio server**

```bash
git add src/mcp_cin7_core/stdio_server.py
git commit -m "feat(stdio): add stdio transport server for Claude Desktop

Add minimal stdio server wrapper that reuses existing FastMCP server.
Enables local testing without OAuth complexity.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Manual verification test

**Files:**
- Read: `.env.example` (to understand required credentials)

**Step 1: Check environment setup**

Verify `.env` exists with required variables:

Run: `grep -E "(CIN7_ACCOUNT_ID|CIN7_API_KEY)" .env`

Expected: Both variables present (values redacted in output)

If `.env` missing, copy from `.env.example` and configure.

**Step 2: Test stdio server starts**

Run: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run python -m mcp_cin7_core.stdio_server`

Expected: JSON response with server capabilities, no exceptions

**Step 3: Verify server identity**

Check that the response includes:
- `"result"` key with server info
- Server name includes "mcp-cin7-core"
- Capabilities list (tools, resources, prompts)

**Step 4: Document verification result**

Add to commit message later: "Manually verified stdio transport responds to initialize request"

---

## Task 3: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md` (in "Running the Server" section)

**Step 1: Add stdio server section to CLAUDE.md**

Find the section `## Running the Server` (after "MCP HTTP Server" section).

Add this new section before "Testing MCP endpoints":

```markdown
### Stdio Server (for Claude Desktop local testing)

```bash
# Run via Python module
uv run python -m mcp_cin7_core.stdio_server
```

The stdio server provides the same MCP tools, resources, and prompts as the HTTP server, but uses stdio transport for direct integration with Claude Desktop.

**Claude Desktop Configuration:**

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
        "mcp_cin7_core.stdio_server"
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

**Environment Variables:**
- Required: `CIN7_ACCOUNT_ID`, `CIN7_API_KEY`
- Optional: `MCP_LOG_LEVEL`, `MCP_LOG_FILE`, `CIN7_BASE_URL`
- Not needed: `AUTH0_*` (stdio uses Cin7 credentials directly, no OAuth)

**Note:** The stdio server is intended for local development and testing only. For production deployments accessible via web, use the HTTP server with OAuth authentication.
```

**Step 2: Verify markdown formatting**

Run: `grep -A 30 "### Stdio Server" CLAUDE.md`

Expected: Section appears correctly formatted

**Step 3: Commit documentation update**

```bash
git add CLAUDE.md
git commit -m "docs: add stdio server usage to CLAUDE.md

Document how to run and configure stdio transport for Claude Desktop.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Update README.md documentation

**Files:**
- Modify: `README.md` (add stdio transport section)

**Step 1: Read current README structure**

Run: `grep "^##" README.md`

Expected: List of section headings to understand structure

**Step 2: Add stdio transport section to README**

Find an appropriate location in README.md (likely after "Installation" or "Usage" section).

Add this section:

```markdown
## Local Development with Claude Desktop

For local testing with Claude Desktop, use the stdio transport:

```bash
uv run python -m mcp_cin7_core.stdio_server
```

Configure in Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cin7-core": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-cin7-core", "run", "python", "-m", "mcp_cin7_core.stdio_server"],
      "env": {
        "CIN7_ACCOUNT_ID": "your-account-id",
        "CIN7_API_KEY": "your-api-key"
      }
    }
  }
}
```

No OAuth configuration needed for local stdio transport. See [CLAUDE.md](CLAUDE.md) for detailed setup instructions.
```

**Step 3: Verify README renders correctly**

Run: `head -50 README.md | grep -A 20 "Local Development"`

Expected: Section appears with correct formatting

**Step 4: Commit README update**

```bash
git add README.md
git commit -m "docs: add stdio transport section to README

Add quick reference for Claude Desktop local setup.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Final verification checklist

**Files:**
- None (verification only)

**Step 1: Verify all files created/modified**

Run: `git log --oneline -4`

Expected: 4 commits visible:
1. feat(stdio): add stdio transport server
2. docs: add stdio server usage to CLAUDE.md
3. docs: add stdio transport section to README
4. (earlier commits from design phase)

**Step 2: Verify no unintended changes to HTTP server**

Run: `git diff main -- src/mcp_cin7_core/http_server.py src/mcp_cin7_core/mcp_server.py src/mcp_cin7_core/cin7_client.py`

Expected: No output (these files unchanged)

**Step 3: Verify clean working directory**

Run: `git status`

Expected: `nothing to commit, working tree clean` or only untracked files like `.env`

**Step 4: Summary check**

Verify implementation completeness:
- [ ] `src/mcp_cin7_core/stdio_server.py` created
- [ ] Module imports successfully
- [ ] CLAUDE.md updated with stdio section
- [ ] README.md updated with stdio section
- [ ] HTTP server files unchanged
- [ ] All changes committed

---

## Post-Implementation: Manual Testing with Claude Desktop

**Note:** This requires Claude Desktop to be installed and configured.

**Step 1: Copy configuration to Claude Desktop**

Location: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

Add the server configuration from CLAUDE.md with your actual project path.

**Step 2: Restart Claude Desktop**

Quit and restart Claude Desktop to load the new server configuration.

**Step 3: Verify server connection**

In Claude Desktop, check for the "cin7-core" server in the available MCP servers list.

Expected: Server appears and shows as connected.

**Step 4: Test basic tool**

In Claude Desktop, ask: "Use cin7_status to check the connection"

Expected: Tool executes and returns Cin7 API status.

**Step 5: Test resource access**

In Claude Desktop, ask: "Read the cin7://templates/product resource"

Expected: Returns product template JSON.

**Step 6: Test prompt access**

In Claude Desktop, ask: "Show me the create_product prompt"

Expected: Returns the product creation workflow guide.

---

## Success Criteria

- [ ] Stdio server runs without errors
- [ ] Server responds to MCP initialize request
- [ ] Documentation updated (CLAUDE.md and README.md)
- [ ] No changes to existing HTTP server code
- [ ] All commits follow conventional commit format
- [ ] Clean git history with descriptive messages
- [ ] Manual testing with Claude Desktop successful (if available)

---

## Rollback Plan

If issues occur:

```bash
# Return to main branch
git checkout main

# Remove worktree
git worktree remove .worktrees/stdio-transport

# Delete feature branch
git branch -D feature/stdio-transport
```

The main branch remains untouched until the feature branch is merged.
