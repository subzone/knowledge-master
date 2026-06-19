# Antigravity Integration

Use Knowledge Master with Antigravity (AI coding assistant).

## Setup

Add to your Antigravity MCP configuration (`~/.config/antigravity/mcp.json` or similar):

```json
{
  "mcpServers": {
    "knowledge-master": {
      "command": "km-server"
    }
  }
}
```

## Available tools

| Tool | Description |
|---|---|
| `search` | Find code, docs, emails by meaning |
| `blast_radius` | "What breaks if I change X?" |
| `safe_to_change` | Risk assessment (safe/risky/dangerous) |
| `who_owns` | File ownership from git blame |
| `check_conventions` | Verify code follows team patterns |
| `index_repo` | Add a repo to knowledge base |
| `index_directory` | Add docs folder |
| `get_status` | Knowledge base stats |

## Example prompts

```
> Search my knowledge base for how we handle JWT token validation

> What's the blast radius if I change the database schema?

> Is it safe to refactor the auth middleware?

> Who currently owns the payment service code?

> Does this new file follow our naming conventions?

> Index my new project at ~/code/new-service
```

## Tips

- Index all your repos first: `km index ~/code/repo1 && km index ~/code/repo2`
- The more you index, the better cross-repo intelligence gets
- Use `km serve` alongside Antigravity to visualize the knowledge graph
