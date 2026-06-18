# CLI Reference

## Commands

| Command | Description |
|---|---|
| `km start` | Start Docker containers + pull Ollama model |
| `km stop` | Stop containers |
| `km index <path>` | Index a git repo or docs directory |
| `km search <query>` | Semantic search with re-ranking |
| `km blast-radius <target>` | Multi-layer dependency analysis |
| `km who-owns <file>` | File ownership (git blame, recency-weighted) |
| `km check-conventions <path>` | Verify code follows detected patterns |
| `km connect <source>` | Pull from external MCP (email, Slack) |
| `km upgrade` | Migrate graph schema to latest version |
| `km prune` | Remove orphaned/stale data |
| `km list` | Show indexed repos, tech stack, stats |
| `km remove <name>` | Remove a source |
| `km serve` | Start web UI (http://127.0.0.1:9999) |
| `km status` | System health check |

## New in v0.4+

### km upgrade

Migrates the graph schema between versions. Runs automatically on connect, but can be triggered manually:

```bash
km upgrade
# Current schema: v3
# Target schema:  v4
# ✓ v3 → v4: Add content_hash to Chunk nodes for deduplication
# ✓ Upgraded to v4
```

### km prune

Removes stale and orphaned data:

```bash
km prune --dry-run          # preview what would be removed
km prune                    # actually remove
km prune --older-than 60    # remove chunks not seen in 60 days
```

### km who-owns

Shows file ownership based on git blame weighted by recency:

```bash
km who-owns src/auth/service.py
# src/auth/service.py
#   Owner: Alex (weight: 0.85)
```

Weighting: last 30 days = 3x, 30-90 days = 2x, older = 1x.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `KM_API_KEY` | API key for REST endpoint auth | None (disabled) |

## Supported languages (static analysis)

| Language | Import resolution | Symbol extraction |
|---|---|---|
| Python | ✅ (stdlib ast) | Functions, classes |
| TypeScript/JS | ✅ (tree-sitter) | Exports, functions, classes |
| Go | ✅ (tree-sitter) | Exported funcs/types (capitalized) |
| Rust | ✅ (tree-sitter) | pub fn/struct/enum, mod |
