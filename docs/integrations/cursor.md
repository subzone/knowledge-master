# Cursor Integration

Add Knowledge Master as an MCP server in Cursor.

## Setup

Create `.cursor/mcp.json` in your project root (or globally at `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "knowledge-master": {
      "command": "km-server"
    }
  }
}
```

Restart Cursor. The tools appear in Cursor's agent mode.

## Usage

In Cursor's chat (Cmd+L), ask:

```
@knowledge-master search for authentication implementation
@knowledge-master what's the blast radius of changing postgres?
@knowledge-master does this project follow our conventions?
```

## Tips

- Index your workspace first: `km index .` in terminal
- The knowledge base persists across Cursor sessions
- Use `km serve` to visualize your knowledge graph while coding
