# Kiro Integration

Add Knowledge Master to your Kiro agent for persistent codebase memory.

## Setup

Create `~/.kiro/agents/knowledge-master.json`:

```json
{
  "name": "knowledge-master",
  "description": "Agent with persistent codebase memory, blast radius analysis, and convention enforcement",
  "prompt": "You have access to a knowledge graph via the 'knowledge' MCP server. Always search before answering questions about code, architecture, or infrastructure. Use blast_radius to check impact of changes. Use check_conventions to verify code follows team patterns. Cite sources from results.",
  "tools": ["read", "write", "shell", "grep", "glob", "code"],
  "mcpServers": {
    "knowledge": {
      "command": "km-server"
    }
  },
  "keyboardShortcut": "ctrl+shift+k",
  "welcomeMessage": "Knowledge base ready. I can search your code, check blast radius, and enforce conventions."
}
```

## Available tools

| Tool | Description |
|---|---|
| `search` | Semantic search with graph context (author, repo, relationships) |
| `blast_radius` | Show what depends on a service, tech, or file |
| `check_conventions` | Verify code follows detected team patterns |
| `index_repo` | Add a new repo to the knowledge base |
| `index_directory` | Add docs/configs to the knowledge base |
| `get_status` | Knowledge base stats |

## Usage

Switch to the agent with `ctrl+shift+k` or `/agent knowledge-master`, then:

```
> What services depend on postgres?
> Does this repo follow our conventions?
> Search for how authentication is implemented
```
