# API Stability

As of v1.0.0, Knowledge Master follows [Semantic Versioning](https://semver.org/).

## Stable (will not break without major version bump)

### MCP Tools

| Tool | Signature | Since |
|---|---|---|
| `search` | `{query: str, top_k?: int, source_type?: str, use_graph?: bool}` | v0.1.0 |
| `blast_radius` | `{target: str}` | v0.2.0 |
| `safe_to_change` | `{target: str}` | v0.6.0 |
| `who_owns` | `{file: str}` | v0.6.0 |
| `check_conventions` | `{path: str}` | v0.2.0 |
| `index_repo` | `{path: str, branch?: str}` | v0.1.0 |
| `index_directory` | `{path: str, patterns?: list}` | v0.1.0 |
| `get_status` | `{}` | v0.1.0 |

### CLI Commands

All commands listed in `km --help` are stable. Arguments and options may gain new optional fields but will not remove or rename existing ones.

### REST API

All `/api/v1/` endpoints are stable. Response shapes will only gain new fields, never remove existing ones.

### Graph Schema

- Schema version is stored in `_Meta` node
- Migrations run automatically on connect
- Existing data is never deleted by migrations

## Experimental (may change in minor versions)

| Feature | Notes |
|---|---|
| `km watch` | File watcher polling strategy may change |
| `km connect` | Connector source configs may be restructured |
| `km changelog` | Output format may change |
| Re-ranking algorithm | May be replaced with a proper cross-encoder |
| Web UI layout | HTML/CSS may change (no API contract on UI) |

## Deprecation policy

- Deprecated features get a warning for 2 minor versions before removal
- Breaking changes require a major version bump (v2.0.0)
