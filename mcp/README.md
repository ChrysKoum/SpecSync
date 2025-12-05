# SpecSync MCP Server

Model Context Protocol server for SpecSync - provides git context and cross-repo Bridge sync tools to Kiro.

## Features

- **Git Context**: Get staged diff for commit-time validation
- **Bridge Tools**: Initialize, sync, validate, and manage API contracts across repos
- **Auto-Detection**: Detect if repo is provider, consumer, or both

## Installation

```bash
npm install -g specsync-mcp
```

## Usage

Add to your Kiro MCP configuration (`.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "specsync": {
      "command": "node",
      "args": ["/path/to/specsync-mcp/dist/server.js"]
    }
  }
}
```

## Tools Provided

- `git_get_staged_diff` - Get commit context
- `bridge_init` - Initialize Bridge
- `bridge_add_dependency` - Add dependency
- `bridge_sync` - Sync contracts
- `bridge_validate` - Validate API calls
- `bridge_status` - Show status
- `bridge_extract` - Extract contract
- `bridge_detect` - Auto-detect role

## License

MIT
