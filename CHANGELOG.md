# Changelog

## Features

- 5fd4975 pyyaml service parsing, git blame ownership, comprehensive tests
- 2b9ffe0 multi-layer blast radius with Python static analysis
- 8b887b3 re-ranking for higher quality search results
- 44e6fac MCP connector framework — index email, Slack, Notion from external MCP servers
- 46f794c REST API, Dockerfile, integration docs for Claude/Cursor/Kiro

## Fixes

- 011cf02 Windows CI — path separators and unicode encoding
- d600183 CI integration tests (start ollama serve), docs workflow (add workflow_dispatch)
- 8dd7a9c address code review — security holes, dead infra, honest README
- a1b7a93 use ollama Client(timeout=30) instead of unsupported request_timeout kwarg
- b06816b lint errors (unused import, f-string without placeholder)

## Documentation

- 8de9b9a add ROADMAP.md (v0.3 → v1.0 plan)
- f8fee41 update CLI reference, blast radius guide, README for new features
- f68c05a add GitHub Pages site with mkdocs-material

## Releases

- 7ee2dad v0.5.0 — platform & testing
- 4c5787a v0.4.0 — reliability & migrations
- 6a499b5 v0.3.0 — multi-language static analysis
- 980abcb v0.2.0

## Other

- 18f86f6 security: harden network, auth, resources, timeouts

