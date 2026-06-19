# Contributing

Thanks for your interest in Knowledge Master! Here's how to get started.

## Development setup

```bash
git clone https://github.com/subzone/knowledge-master.git
cd knowledge-master
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
km start
```

## Running tests

```bash
# Unit tests (no Docker/Ollama needed)
pytest tests/ --ignore=tests/integration

# Integration tests (requires Docker + Ollama running)
pytest tests/integration/

# Lint
ruff check knowledge_master/
```

## Project structure

```
knowledge_master/
├── cli.py              # Typer CLI (14 commands)
├── server.py           # MCP server (8 tools)
├── api.py              # REST API (/api/v1/)
├── web.py              # Web UI (FastAPI + htmx)
├── store.py            # FalkorDB graph operations
├── embeddings.py       # Ollama embedding client
├── rerank.py           # Re-ranking logic
├── chunking.py         # Smart text splitting by language
├── intelligence.py     # Tech stack, services, conventions, ownership
├── static_analysis.py  # AST/tree-sitter import graph extraction
├── ts_parsers.py       # Tree-sitter parsers (TS, Go, Rust, Java, C#, Terraform)
├── connectors.py       # External MCP server connectors
├── migrations.py       # Schema versioning and migrations
└── watcher.py          # File watcher for incremental indexing
```

## Making changes

1. Fork the repo
2. Create a branch (`git checkout -b feat/my-feature`)
3. Make changes
4. Run `ruff check knowledge_master/ --fix` and `pytest tests/ --ignore=tests/integration`
5. Commit with conventional prefix: `feat:`, `fix:`, `docs:`, `test:`
6. Open a PR

## Adding a new language parser

1. Add tree-sitter grammar to `pyproject.toml`
2. Create extraction function in `ts_parsers.py` (follow `extract_go_graph` pattern)
3. Add builder function in `static_analysis.py` (follow `_build_go_import_graph` pattern)
4. Register in `build_import_graph_all()`
5. Add extension to `INDEXABLE_EXTENSIONS` in `parsers/git_repo.py`
6. Add extension to `LANGUAGE_MAP` in `chunking.py`
7. Add a test in `tests/test_ts_parsers.py`

## Adding a new MCP tool

1. Add `Tool()` definition in `server.py` → `list_tools()`
2. Add handler in `server.py` → `call_tool()`
3. Optionally add CLI command in `cli.py`
4. Optionally add REST endpoint in `api.py`
5. Document in `STABILITY.md` (experimental or stable)
