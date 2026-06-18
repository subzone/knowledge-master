# Security

Knowledge Master is designed to run **locally on your machine**. No data is sent to external services. This document covers the security model, risks, and hardening options.

## Architecture security

```
┌─────────────────────────────────────────────────┐
│                  Your Machine                    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  FalkorDB (127.0.0.1:6379)             │    │  ← localhost only
│  │  Stores: graph nodes, vectors, text     │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  Web UI / REST API (127.0.0.1:9999)    │    │  ← localhost only
│  │  Optional API key auth                  │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  Ollama (localhost:11434)               │    │  ← local inference
│  │  No data sent externally                │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  MCP Server (stdio)                     │    │  ← no network
│  │  Only accessible to parent process      │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
      ↕ NOTHING leaves this boundary
```

## What data is stored

| Data type | Storage | Encryption | Notes |
|---|---|---|---|
| Code chunks | FalkorDB (Docker volume) | None (plaintext) | Text snippets from indexed files |
| Embeddings | FalkorDB (Docker volume) | None | 768-dim float vectors |
| Email content | FalkorDB (Docker volume) | None (plaintext) | If you use `km connect outlook` |
| Graph metadata | FalkorDB (Docker volume) | None | Authors, repos, services, tech stack |
| Postgres | Docker volume | None | Metadata and state |

## Network exposure

All ports are bound to `127.0.0.1` (localhost only). No service is accessible from your LAN or the internet by default.

| Service | Port | Binding | Auth |
|---|---|---|---|
| FalkorDB | 6379 | `127.0.0.1` only | None (Redis protocol) |
| Postgres | 5433 | `127.0.0.1` only | Password (env var) |
| Web UI | 9999 | `127.0.0.1` only | Optional API key |
| Ollama | 11434 | Managed by Ollama | None |

## Hardening

### Enable API key auth

```bash
export KM_API_KEY=$(openssl rand -hex 32)
km serve
```

REST API calls then require:
```bash
curl -H "X-API-Key: $KM_API_KEY" http://127.0.0.1:9999/api/v1/search?q=test
```

The web UI pages (`/`, `/graph`) remain accessible without auth for local browser use.

### Change Postgres password

```bash
export KM_PG_PASSWORD=$(openssl rand -hex 16)
km start
```

### Encrypt Docker volumes

On macOS, Docker Desktop encrypts volumes by default (FileVault). On Linux:

```bash
# Use encrypted filesystem for Docker volumes
sudo cryptsetup luksFormat /dev/sdX
```

### Restrict FalkorDB access

If you need additional isolation:

```bash
# Only allow connections from the km process
docker network create km-internal --internal
```

## Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Local process reads indexed emails | Medium | High | Enable `KM_API_KEY` auth |
| Docker volume stolen (laptop theft) | Low | High | Enable disk encryption (FileVault/LUKS) |
| Malicious dependency in supply chain | Low | Critical | Pin versions, review updates |
| Ollama sends data externally | Very low | High | Ollama is local-only by default |
| Browser extension hits localhost API | Medium | Medium | API key auth blocks unauthorized access |
| Shared machine — other users access | Medium | High | Run in user-namespaced Docker, enable auth |

## What we do NOT do

- ❌ No telemetry or analytics
- ❌ No data sent to any cloud service
- ❌ No account creation required
- ❌ No external API calls (except Ollama on localhost)
- ❌ No cookies or session tracking in web UI

## Reporting vulnerabilities

Email security concerns to the repository owner. Do not open public issues for security vulnerabilities.

## Dependencies

All dependencies are pinned with minimum version ranges. Key packages:

| Package | Purpose | Trust level |
|---|---|---|
| `falkordb` | Graph DB client | Official FalkorDB team |
| `ollama` | Embedding model client | Official Ollama team |
| `mcp` | MCP protocol | Anthropic |
| `fastapi` | REST API / Web | Widely trusted, 70k+ stars |
| `gitpython` | Git integration | Established, 4k+ stars |
| `typer` | CLI framework | Same author as FastAPI |
| `rich` | Terminal output | Widely trusted, 50k+ stars |
