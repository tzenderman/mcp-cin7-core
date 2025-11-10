# Stdio Transport Design

**Date**: 2025-11-10
**Status**: Approved

## Overview

Add stdio transport support to the MCP Cin7 Core server to enable local testing with Claude Desktop, without affecting the existing HTTP server deployment.

## Goals

- Enable local development and testing via stdio transport
- Zero impact on existing HTTP server
- No code duplication
- Simple configuration for Claude Desktop users

## Non-Goals

- OAuth authentication for stdio (local testing only needs Cin7 credentials)
- Changing existing HTTP server behavior
- Creating a unified entrypoint that supports both transports

## Architecture

### High-Level Approach

Create a minimal stdio server wrapper that reuses the existing FastMCP server instance from `mcp_server.py`. The FastMCP framework already supports multiple transports, so we simply run the same server with a different transport.

### Component Overview

```
src/mcp_cin7_core/
├── cin7_client.py       (unchanged)
├── mcp_server.py        (unchanged - exports server)
├── http_server.py       (unchanged)
└── stdio_server.py      (NEW - stdio wrapper)
```

### Key Design Decisions

**Decision 1: Import existing server vs. create new one**
- **Chosen**: Import existing server
- **Rationale**: Eliminates code duplication, ensures identical behavior across transports
- **Trade-off**: Slight coupling, but acceptable since both transports need same MCP functionality

**Decision 2: Authentication approach**
- **Chosen**: No OAuth for stdio transport
- **Rationale**: Stdio is for local testing only; OAuth adds unnecessary complexity
- **Security**: Relies on Cin7 API credentials from .env file

**Decision 3: Launch mechanism**
- **Chosen**: Python module invocation (`python -m mcp_cin7_core.stdio_server`)
- **Rationale**: Simplest for users, no need to modify pyproject.toml scripts
- **Alternative considered**: Separate CLI command (rejected as overkill for testing tool)

## Implementation

### New File: `src/mcp_cin7_core/stdio_server.py`

```python
from .mcp_server import server

def main():
    """Run the MCP server using stdio transport for Claude Desktop."""
    server.run(transport="stdio")

if __name__ == "__main__":
    main()
```

### Environment Configuration

**Required for stdio**:
- `CIN7_ACCOUNT_ID` - Cin7 Core account identifier
- `CIN7_API_KEY` - Cin7 Core API key

**Optional**:
- `MCP_LOG_LEVEL` - Logging verbosity (default: INFO)
- `MCP_LOG_FILE` - Log file path with rotation
- `CIN7_BASE_URL` - API base URL (defaults to production)

**Not needed for stdio**:
- `AUTH0_*` - OAuth not used in stdio transport
- `TOKEN_CACHE_*` - No token caching needed
- `MCP_SERVER_URL` - Only needed for HTTP OAuth

### Claude Desktop Configuration

Users add this to their `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cin7-core": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-cin7-core",
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

## Testing Strategy

### Manual Testing
1. Configure Claude Desktop with stdio server
2. Verify connection established
3. Test basic tools: `cin7_status`, `cin7_products`
4. Test resources: `cin7://templates/product`
5. Verify logging output

### Verification Checklist
- [ ] Stdio server starts without errors
- [ ] All tools callable and return correct data
- [ ] All resources readable
- [ ] All prompts accessible
- [ ] Logging works at different levels
- [ ] HTTP server still works unchanged

## Documentation Updates

### CLAUDE.md additions:

```markdown
### Stdio Server (for Claude Desktop local testing)

```bash
# Run via Python module
python -m mcp_cin7_core.stdio_server
```

Configure in Claude Desktop:
```json
{
  "mcpServers": {
    "cin7-core": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-cin7-core", "run", "python", "-m", "mcp_cin7_core.stdio_server"],
      "env": {
        "CIN7_ACCOUNT_ID": "...",
        "CIN7_API_KEY": "..."
      }
    }
  }
}
```

No OAuth required - uses Cin7 credentials directly from environment.
```

### README.md additions:

Add section on local development workflow with Claude Desktop.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking HTTP server | High | No changes to http_server.py, thorough testing |
| Logging conflicts between transports | Low | Logging already configured in mcp_server.py |
| Missing dependencies for stdio | Medium | FastMCP already includes stdio support |
| Users confused about which transport to use | Low | Clear documentation on use cases |

## Success Criteria

- [ ] Stdio server runs successfully with Claude Desktop
- [ ] All existing tools/resources/prompts work identically
- [ ] HTTP server continues working without changes
- [ ] Documentation clearly explains both deployment options
- [ ] Zero code duplication between transports

## Future Considerations

- Could add unified entrypoint with `--transport` flag if needed
- Could add optional OAuth support for stdio if use case emerges
- Could create shell script wrapper for easier Claude Desktop setup
