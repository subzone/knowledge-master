# I Built a Local Knowledge Graph That Tells AI Agents "What Breaks If I Change This?"

Every time I start a new AI coding session, the same thing happens: I re-explain my architecture, my conventions, my service dependencies. The AI doesn't remember. It doesn't know that `store.py` is imported by 8 other modules, that Milenko owns the auth service, or that postgres is a single point of failure.

So I built **Knowledge Master** — a local knowledge graph that gives AI agents permanent memory of your codebase.

## What makes it different from "just another RAG"

Most RAG tools embed your code into vectors and return "similar chunks." That's fancy grep. It doesn't understand relationships.

Knowledge Master builds an actual **graph**:

```
Repo → USES_TECH → Python, FastAPI, Docker
Repo → DEFINES_SERVICE → auth-service → DEPENDS_ON → postgres
Person → AUTHORED → Document → IMPORTS → Document
Function → DEFINED_IN → File → IN_REPO → Repo
```

This lets it answer questions that flat search can't:

### "What breaks if I change this?"

```bash
$ km blast-radius store.py
💥 Blast radius: store.py
├── Definite impact
│   ├── 📄 cli.py (IMPORTS)
│   ├── 📄 server.py (IMPORTS)
│   ├── 📄 web.py (IMPORTS)
│   ├── 📄 api.py (IMPORTS)
│   └── 📄 connectors.py (IMPORTS)
├── Likely affected
│   └── ⚙️ falkordb (Service, owns affected file)
└── Possibly affected
    └── 👤 Milenko (Person, AUTHORED affected file)
```

This uses **real static analysis** — Python AST, tree-sitter for TypeScript/Go/Rust/Java/C# — to trace actual import dependencies. Not text similarity.

### "Is it safe to touch this?"

```bash
$ km safe-to-change auth/service.py
Risk: RISKY
├── Blast radius: 12 entities
├── Test coverage: yes (3 test files)
└── Affected: api.py, gateway.py, user-service...
```

Combines blast radius + test coverage detection into a risk score: **safe / risky / dangerous**.

### "Who owns this code?"

```bash
$ km who-owns src/payments/stripe.py
Owner: Alex (weight: 0.85)
```

Git blame weighted by recency — recent changes count more than ancient history.

## How it works

```
Your repos
    ↓ km index
┌─────────────────────────────┐
│  FalkorDB (Graph + Vector)  │
│                             │
│  Nodes: Repo, Document,    │
│  Person, Service, Tech,    │
│  Function, Convention      │
│                             │
│  Edges: IMPORTS, DEPENDS_ON,│
│  AUTHORED, OWNS, USES_TECH │
│                             │
│  + Vector embeddings for    │
│    semantic search          │
└─────────────────────────────┘
    ↓ MCP protocol
Your AI agent (Claude, Cursor, Copilot, Kiro)
```

Everything runs locally:
- **FalkorDB** — graph database with built-in vector search (single Docker container)
- **Ollama** — local embeddings (nomic-embed-text, 274MB)
- **Tree-sitter** — structural code parsing for 7 languages
- **No cloud, no API keys, no data leaves your machine**

## 7 Languages supported

| Language | Static Analysis |
|---|---|
| Python | AST import graph, function/class extraction |
| TypeScript/JS | tree-sitter imports, exports |
| Go | tree-sitter imports, exported functions/types |
| Rust | tree-sitter use/mod, pub items |
| Java | tree-sitter imports, public classes/methods |
| C# | tree-sitter using directives, public members |
| Terraform | Module dependencies, resource/variable extraction |

## MCP Server — AI agents use it directly

Knowledge Master exposes 8 tools via the Model Context Protocol:

| Tool | What the AI agent can do |
|---|---|
| `search` | Semantic search with re-ranking |
| `blast_radius` | "What breaks if I change X?" |
| `safe_to_change` | Risk assessment |
| `who_owns` | File ownership |
| `check_conventions` | "Does this follow our patterns?" |
| `index_repo` | Add a new repo |
| `index_directory` | Add docs |
| `get_status` | Knowledge base stats |

Setup for any AI tool is one command:

```bash
km setup cursor    # or claude, kiro, copilot, amazonq
```

## Try it

```bash
pipx install knowledge-master
km start
km index ~/your-project
km search "how does authentication work"
km blast-radius auth/service.py
km safe-to-change auth/service.py
km serve  # web UI with graph visualization
```

## Links

- **GitHub**: [github.com/subzone/knowledge-master](https://github.com/subzone/knowledge-master)
- **PyPI**: `pipx install knowledge-master`
- **Docs**: [subzone.github.io/knowledge-master](https://subzone.github.io/knowledge-master)

---

I'd love feedback — especially on:
- What languages/frameworks should be prioritized next?
- Would you prefer deeper call-graph analysis or more connectors (Slack, Jira)?
- Is the MCP integration the right bet, or would a VS Code extension be more useful?

MIT licensed, open source, built for developers who are tired of re-explaining their codebase to AI.
