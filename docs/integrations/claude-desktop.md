# Claude Desktop Integration

Add Knowledge Master as an MCP server in Claude Desktop.

## Setup

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "knowledge-master": {
      "command": "km-server"
    }
  }
}
```

Restart Claude Desktop. You'll see the tools available in the 🔨 menu.

## Available tools

- **search** — Semantic search across your indexed repos and docs
- **blast_radius** — "What depends on X?" dependency analysis
- **check_conventions** — Verify code follows your team's patterns
- **index_repo** — Index a git repository
- **index_directory** — Index a docs folder
- **get_status** — Check what's indexed

## Example prompts

```
Search my knowledge base for how we handle JWT tokens
What's the blast radius if I change the auth-service?
Check if ~/new-project follows our conventions
```
