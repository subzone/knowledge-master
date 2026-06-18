# Roadmap

## ✅ v0.2.0 — Security & Polish (Released)

- [x] Multi-layer blast radius with confidence levels
- [x] Git blame ownership (recency-weighted)
- [x] `km who-owns` command
- [x] `km connect` (MCP connector for email/Slack)
- [x] REST API with OpenAPI docs
- [x] Re-ranking for search quality
- [x] Security hardening (localhost bind, API key auth)
- [x] 12 unit tests, GitHub Actions CI
- [x] Documentation site (mkdocs-material)

## ✅ v0.3.0 — Multi-language Static Analysis (Released)

- [x] TypeScript/JavaScript import graph (tree-sitter)
- [x] Go import graph (tree-sitter)
- [x] Rust use/mod graph (tree-sitter)
- [x] Unified `build_import_graph_all()` — dispatch by extension
- [x] Blast radius works cross-language

## ✅ v0.4.0 — Reliability & Migrations (Released)

- [x] Schema versioning (stored in graph metadata)
- [x] `km upgrade` command (auto-migrates between versions)
- [x] Error recovery (per-file isolation, >50% failure warning)
- [x] Deduplication via content hash (skips unchanged chunks)
- [x] `km prune` — remove orphaned/stale data

## ✅ v0.5.0 — Platform & Testing (Released)

- [x] Windows CI (GitHub Actions matrix)
- [x] 37 unit tests covering all modules
- [x] Re-ranker benchmark tests (cosine similarity)
- [x] Tree-sitter parser tests (TS, Go, Rust)
- [x] Connector and migration tests

## 🚧 v0.6.0 — Advanced Features (Next)

- [ ] `km safe-to-change <target>` (blast radius + test coverage = risk score)
- [ ] Cross-repo dependency resolution (pip/npm packages → linked repos)
- [ ] Scheduled sync (cron-based re-indexing)
- [ ] CHANGELOG.md (auto-generated from conventional commits)
- [ ] Function-level call graph (who calls this function?)

## 🔮 v1.0.0 — Stable Release

- [ ] Stable API contract (semver guarantees)
- [ ] Published to MCP registry
- [ ] Homebrew tap (`brew install knowledge-master`)
- [ ] VS Code extension
- [ ] 80%+ test coverage on core modules
- [ ] Battle-tested on 10+ diverse repos
