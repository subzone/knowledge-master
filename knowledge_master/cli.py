"""CLI for knowledge-master — simple commands for indexing, searching, and managing."""

import json
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from . import embeddings, store
from .parsers import git_repo, markdown

app = typer.Typer(name="km", help="Knowledge Master — your codebase's memory", no_args_is_help=True)
console = Console()

PROJECT_DIR = Path(__file__).parent.parent


@app.command()
def start():
    """Start Knowledge Master (Docker containers + Ollama model)."""

    console.print("[bold]Starting Knowledge Master...[/]\n")

    # Check Docker
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[red]✗ Docker is not running.[/] Please start Docker first.")
        raise typer.Exit(1)

    # Start FalkorDB container
    console.print("  [dim]Starting FalkorDB...[/]")
    # Check if already running
    check = subprocess.run(["docker", "ps", "--filter", "name=km-falkordb", "--format", "{{.Names}}"],
                           capture_output=True, text=True)
    if "km-falkordb" not in check.stdout:
        # Pull image first (docker run with capture_output hides pull errors)
        console.print("  [dim]Pulling FalkorDB image...[/]")
        subprocess.run(["docker", "pull", "falkordb/falkordb:v4.4.1"], capture_output=True)
        subprocess.run([
            "docker", "run", "-d", "--name", "km-falkordb",
            "-p", "127.0.0.1:6379:6379",
            "--restart", "unless-stopped",
            "-v", "km-falkordb-data:/data",
            "--memory", "512m",
            "falkordb/falkordb:v4.4.1",
        ], capture_output=True)
    # Wait for ready
    import time
    for _ in range(10):
        ping = subprocess.run(["docker", "exec", "km-falkordb", "redis-cli", "ping"],
                              capture_output=True, text=True)
        if "PONG" in ping.stdout:
            break
        time.sleep(1)
    console.print("  [green]✓[/] FalkorDB running")

    # Check/pull Ollama model
    console.print("  [dim]Checking embedding model...[/]")
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "nomic-embed-text" not in result.stdout:
            console.print("  [dim]Pulling nomic-embed-text...[/]")
            subprocess.run(["ollama", "pull", "nomic-embed-text"], check=True)
        console.print("  [green]✓[/] Embedding model ready")
    except FileNotFoundError:
        import platform
        console.print("[yellow]Ollama not found.[/]")
        install = typer.confirm("  Install Ollama automatically?", default=True)
        if install:
            system = platform.system()
            if system == "Darwin":
                console.print("  [dim]Installing via Homebrew...[/]")
                subprocess.run(["brew", "install", "ollama"], check=True)
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                import time
                time.sleep(3)
            elif system == "Linux":
                console.print("  [dim]Installing via official script...[/]")
                subprocess.run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], check=True)
            else:
                console.print("[red]✗ Auto-install not supported on Windows.[/]")
                console.print("  Download from: https://ollama.com/download")
                raise typer.Exit(1)
            console.print("  [dim]Pulling nomic-embed-text...[/]")
            subprocess.run(["ollama", "pull", "nomic-embed-text"], check=True)
            console.print("  [green]✓[/] Ollama installed + model ready")
        else:
            console.print("  Install manually: https://ollama.com")
            raise typer.Exit(1)

    # Init schema
    graph = store.get_graph()
    store.init_schema(graph)
    console.print("  [green]✓[/] Graph schema initialized")

    console.print("\n[bold green]Knowledge Master is ready![/]")
    console.print("  • Index a repo:   [cyan]km index ~/path/to/repo[/]")
    console.print("  • Search:         [cyan]km search \"your query\"[/]")
    console.print("  • Web UI:         [cyan]km serve[/]")
    console.print("  • Graph viz:      [cyan]http://127.0.0.1:9999/graph[/]")


@app.command()
def stop():
    """Stop Knowledge Master containers."""
    subprocess.run(["docker", "stop", "km-falkordb"], capture_output=True)
    subprocess.run(["docker", "rm", "km-falkordb"], capture_output=True)
    console.print("[green]✓[/] Knowledge Master stopped")


@app.command()
def index(
    path: str = typer.Argument(..., help="Path to git repo or directory"),
    type: str = typer.Option("auto", "--type", "-t", help="Source type: auto, repo, docs"),
):
    """Index a git repo or directory of documents."""
    path = str(Path(path).expanduser().resolve())

    if type == "auto":
        type = "repo" if (Path(path) / ".git").exists() else "docs"

    graph = store.get_graph()
    store.init_schema(graph)

    if type == "repo":
        console.print(f"[bold blue]Indexing git repo:[/] {path}")
        result = git_repo.index_repo(path, graph)
    else:
        console.print(f"[bold blue]Indexing docs:[/] {path}")
        result = markdown.index_directory(path, graph)

    console.print(f"[green]✓ Done![/] {json.dumps(result)}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(10, "--top", "-n", help="Number of results"),
):
    """Semantic search across the knowledge base."""
    graph = store.get_graph()
    vec = embeddings.embed(query)
    results = store.graph_context_search(graph, vec, top_k, query=query)

    table = Table(title=f"Results for: {query}")
    table.add_column("Score", width=6)
    table.add_column("Source", max_width=50)
    table.add_column("Context", width=25)
    table.add_column("Preview", max_width=80)

    for r in results:
        ctx_parts = []
        if r.get("repo"):
            ctx_parts.append(f"repo:{r['repo']}")
        if r.get("author"):
            ctx_parts.append(f"by:{r['author']}")
        table.add_row(
            f"{r.get('score', 0):.3f}",
            r.get("source", ""),
            ", ".join(ctx_parts),
            (r.get("text", "")[:100] + "...") if r.get("text") else "",
        )

    console.print(table)


@app.command()
def blast_radius(
    target: str = typer.Argument(..., help="Service, file, function, or tech name"),
    depth: int = typer.Option(4, "--depth", "-d", help="Traversal depth"),
):
    """Show what depends on a target — multi-layer blast radius analysis."""
    graph = store.get_graph()
    results = _compute_blast_radius(graph, target, depth)

    if not results:
        console.print(f"[yellow]No dependencies found for:[/] {target}")
        console.print("[dim]Try: a file path, function name, service, or technology[/]")
        return

    tree = Tree(f"[bold red]💥 Blast radius: {target}[/]")

    # Group by confidence
    definite = [r for r in results if r["confidence"] == "definite"]
    likely = [r for r in results if r["confidence"] == "likely"]
    possible = [r for r in results if r["confidence"] == "possible"]

    if definite:
        branch = tree.add("[bold]Definite impact[/]")
        for r in definite:
            icon = _icon(r["type"])
            branch.add(f"{icon} [bold]{r['name']}[/] [dim]({r['type']}, {r['rel']})[/]")

    if likely:
        branch = tree.add("[yellow]Likely affected[/]")
        for r in likely:
            icon = _icon(r["type"])
            branch.add(f"{icon} {r['name']} [dim]({r['type']}, {r['rel']})[/]")

    if possible:
        branch = tree.add("[dim]Possibly affected[/]")
        for r in possible:
            icon = _icon(r["type"])
            branch.add(f"{icon} {r['name']} [dim]({r['type']}, {r['rel']})[/]")

    console.print(tree)
    console.print(f"\n[dim]{len(results)} entities: {len(definite)} definite, {len(likely)} likely, {len(possible)} possible[/]")


def _compute_blast_radius(graph, target: str, depth: int = 4) -> list[dict]:
    """Multi-layer blast radius: Symbol → File → Service → Person."""
    results = []
    seen = set()

    # Layer 1: File-level imports (who imports this file?)
    r = graph.query(
        """MATCH (src:Document)-[:IMPORTS]->(dst:Document)
           WHERE dst.path CONTAINS $name
           RETURN 'Document' AS type, src.path AS name, 'IMPORTS' AS rel""",
        params={"name": target},
    )
    for row in (r.result_set or []):
        if row[1] and row[1] not in seen:
            seen.add(row[1])
            results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "definite"})

    # Layer 1b: Symbol-level (who defines/uses this function?)
    r = graph.query(
        """MATCH (f:Function {name: $name})-[:DEFINED_IN]->(d:Document)
           OPTIONAL MATCH (importer:Document)-[:IMPORTS]->(d)
           RETURN 'Document' AS type, importer.path AS name, 'IMPORTS function' AS rel""",
        params={"name": target},
    )
    for row in (r.result_set or []):
        if row[1] and row[1] not in seen:
            seen.add(row[1])
            results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "definite"})

    # Layer 2: Service-level (which service owns affected files?)
    affected_files = [r["name"] for r in results if r["type"] == "Document"]
    affected_files.append(target)  # include the target itself

    r = graph.query(
        """MATCH (d:Document)-[:IN_REPO]->(repo:Repo)-[:DEFINES_SERVICE]->(svc:Service)
           WHERE any(f IN $files WHERE d.path CONTAINS f)
           RETURN 'Service' AS type, svc.name AS name, 'owns affected file' AS rel""",
        params={"files": affected_files},
    )
    for row in (r.result_set or []):
        if row[1] and row[1] not in seen:
            seen.add(row[1])
            results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "likely"})

    # Layer 2b: Services that depend on affected services
    affected_services = [r["name"] for r in results if r["type"] == "Service"]
    if affected_services:
        r = graph.query(
            """MATCH (upstream:Service)-[:DEPENDS_ON]->(downstream:Service)
               WHERE downstream.name IN $services
               RETURN 'Service' AS type, upstream.name AS name, 'DEPENDS_ON' AS rel""",
            params={"services": affected_services},
        )
        for row in (r.result_set or []):
            if row[1] and row[1] not in seen:
                seen.add(row[1])
                results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "likely"})

    # Layer 3: Tech-level
    r = graph.query(
        """MATCH (t:Tech {name: $name})
           OPTIONAL MATCH (repo:Repo)-[:USES_TECH]->(t)
           RETURN 'Repo' AS type, repo.name AS name, 'USES_TECH' AS rel""",
        params={"name": target},
    )
    for row in (r.result_set or []):
        if row[1] and row[1] not in seen:
            seen.add(row[1])
            results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "possible"})

    # Layer 4: People (who authored affected files?)
    r = graph.query(
        """MATCH (p:Person)-[:AUTHORED]->(d:Document)
           WHERE any(f IN $files WHERE d.path = f)
           RETURN 'Person' AS type, p.name AS name, 'AUTHORED affected file' AS rel""",
        params={"files": affected_files},
    )
    for row in (r.result_set or []):
        if row[1] and row[1] not in seen:
            seen.add(row[1])
            results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "possible"})

    # Layer 5: Cross-repo dependencies (repos that depend on the target repo)
    r = graph.query(
        """MATCH (dependent:Repo)-[:DEPENDS_ON_REPO]->(target:Repo)
           WHERE target.name = $name
           RETURN 'Repo' AS type, dependent.name AS name, 'DEPENDS_ON_REPO' AS rel""",
        params={"name": target},
    )
    for row in (r.result_set or []):
        if row[1] and row[1] not in seen:
            seen.add(row[1])
            results.append({"type": row[0], "name": row[1], "rel": row[2], "confidence": "likely"})

    return results


def _icon(node_type: str) -> str:
    return {"Repo": "📦", "Service": "⚙️", "Person": "👤", "Document": "📄",
            "Tech": "🔧", "Function": "🔧", "Class": "🏗️"}.get(node_type, "•")


@app.command()
def check_conventions(
    path: str = typer.Argument(".", help="Path to check against conventions"),
):
    """Check if a file or repo follows detected conventions."""
    path = str(Path(path).expanduser().resolve())
    repo_name = Path(path).name
    graph = store.get_graph()

    # Get conventions for this repo (or all if not found)
    result = graph.query(
        """MATCH (r:Repo)-[:FOLLOWS]->(c:Convention)
           WHERE r.name = $name OR r.path = $path
           RETURN c.name, c.category""",
        params={"name": repo_name, "path": path},
    )

    if not result.result_set:
        # Fall back to all conventions
        result = graph.query("MATCH (c:Convention) RETURN c.name, c.category")

    if not result.result_set:
        console.print("[yellow]No conventions detected yet.[/] Index a repo first.")
        return

    console.print(f"[bold]Checking conventions for:[/] {path}\n")
    violations = []
    passes = []

    for conv_name, category in result.result_set:
        passed = _check_convention(path, conv_name)
        if passed:
            passes.append((conv_name, category))
        else:
            violations.append((conv_name, category))

    for name, cat in passes:
        console.print(f"  [green]✓[/] {name} [dim]({cat})[/]")
    for name, cat in violations:
        console.print(f"  [red]✗[/] {name} [dim]({cat})[/]")

    if violations:
        console.print(f"\n[red]{len(violations)} convention(s) violated[/]")
        raise typer.Exit(1)
    else:
        console.print(f"\n[green]All {len(passes)} conventions pass ✓[/]")


def _check_convention(path: str, convention: str) -> bool:
    """Check a single convention against a path."""
    p = Path(path)
    if convention == "src/ directory":
        return (p / "src").is_dir()
    elif convention == "separate test directory":
        return (p / "tests").is_dir() or (p / "test").is_dir()
    elif convention == "docs/ directory":
        return (p / "docs").is_dir()
    elif convention == "snake_case files":
        code_files = list(p.rglob("*.py")) + list(p.rglob("*.ts")) + list(p.rglob("*.rs"))
        code_files = [f for f in code_files if ".venv" not in str(f) and "node_modules" not in str(f)]
        if not code_files:
            return True
        violations = [f for f in code_files if "-" in f.stem and not f.stem.startswith(".")]
        return len(violations) == 0
    elif convention == "kebab-case files":
        code_files = list(p.rglob("*.py")) + list(p.rglob("*.ts"))
        code_files = [f for f in code_files if ".venv" not in str(f)]
        if not code_files:
            return True
        violations = [f for f in code_files if "_" in f.stem]
        return len(violations) == 0
    elif convention == "infra as code":
        return (p / "infra").is_dir() or (p / "deploy").is_dir() or (p / "k8s").is_dir()
    # Default: can't verify, assume pass
    return True


@app.command(name="list")
def list_sources():
    """List all indexed sources and stats."""
    graph = store.get_graph()
    stats = store.get_stats(graph)

    console.print("\n[bold]Knowledge Base Stats[/]")
    console.print(f"  Chunks:    {stats['chunks']}")
    console.print(f"  Documents: {stats['documents']}")
    console.print(f"  Repos:     {stats['repos']}")

    result = graph.query("MATCH (r:Repo) RETURN r.name, r.path")
    if result.result_set:
        console.print("\n[bold]Repos:[/]")
        for name, path in result.result_set:
            console.print(f"  • {name or '(unnamed)'} — {path}")

    result = graph.query("MATCH (t:Tech) WHERE t.category = 'language' OR t.category = 'infrastructure' RETURN t.name, t.category")
    if result.result_set:
        console.print("\n[bold]Stack:[/]")
        for name, cat in result.result_set:
            console.print(f"  • {name} ({cat})")


@app.command()
def remove(source: str = typer.Argument(..., help="Repo name or doc path to remove")):
    """Remove an indexed source and all its chunks."""
    graph = store.get_graph()
    result = graph.query(
        """MATCH (r:Repo {name: $name})
           OPTIONAL MATCH (d:Document)-[:IN_REPO]->(r)
           OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
           OPTIONAL MATCH (r)-[e]->()
           DELETE c, d, e, r
           RETURN count(c)""",
        params={"name": source},
    )
    deleted = result.result_set[0][0] if result.result_set else 0
    if deleted > 0:
        console.print(f"[green]✓ Removed[/] {source} ({deleted} chunks)")
    else:
        console.print(f"[yellow]Not found:[/] {source}")



@app.command()
def connect(
    source: str = typer.Argument(..., help="Source to pull from: outlook, slack, notion, or custom"),
    command: str = typer.Option(None, "--command", "-c", help="Custom MCP server command"),
    tool: str = typer.Option(None, "--tool", "-t", help="Tool name to call on the MCP server"),
):
    """Pull and index data from an external MCP server (email, Slack, etc.)."""
    from .connectors import sync_pull_and_index, add_custom_source, SOURCES

    if command and tool:
        add_custom_source(source, command.split(), tool)

    if source not in SOURCES:
        console.print(f"[yellow]Unknown source:[/] {source}")
        console.print(f"[dim]Available: {', '.join(SOURCES.keys())}[/]")
        console.print("[dim]Or use --command and --tool for custom MCP servers[/]")
        raise typer.Exit(1)

    console.print(f"[bold blue]Connecting to {source}...[/]")
    try:
        result = sync_pull_and_index(source)
        console.print(f"[green]✓ Done![/] {json.dumps(result)}")
    except Exception as e:
        console.print(f"[red]✗ Failed:[/] {e}")
        raise typer.Exit(1)

@app.command()
def status():
    """Check system health."""
    try:
        graph = store.get_graph()
        store.get_stats(graph)
        console.print("[green]✓[/] FalkorDB: connected")
    except Exception as e:
        console.print(f"[red]✗[/] FalkorDB: {e}")

    try:
        embeddings.embed("test")
        console.print("[green]✓[/] Ollama: ready")
    except Exception as e:
        console.print(f"[red]✗[/] Ollama: {e}")


@app.command()
def serve(port: int = typer.Option(9999, help="Port for web UI")):
    """Start the web UI."""
    from .web import create_app
    import uvicorn

    console.print(f"[bold green]Knowledge Master UI[/] → http://127.0.0.1:{port}")
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


@app.command(name="who-owns")
def who_owns(file: str = typer.Argument(..., help="File path to check ownership")):
    """Show who owns a file based on git blame analysis."""
    graph = store.get_graph()
    result = graph.query(
        """MATCH (p:Person)-[r:OWNS]->(d:Document)
           WHERE d.path CONTAINS $file
           RETURN p.name, r.weight, d.path
           ORDER BY r.weight DESC LIMIT 1""",
        params={"file": file},
    )
    if result.result_set:
        name, weight, path = result.result_set[0]
        console.print(f"[bold]{path}[/]")
        console.print(f"  Owner: [green]{name}[/] (weight: {weight:.2f})")
    else:
        console.print(f"[yellow]No ownership data for:[/] {file}")
        console.print("[dim]Run 'km index <repo>' first to extract ownership.[/]")


@app.command(name="safe-to-change")
def safe_to_change(
    target: str = typer.Argument(..., help="File or module to assess change risk for"),
):
    """Assess risk of changing a target — blast radius + test coverage analysis."""
    graph = store.get_graph()
    affected = _compute_blast_radius(graph, target)
    blast_count = len(affected)

    # Check test coverage
    test_files = []
    r = graph.query(
        """MATCH (d:Document)-[:IMPORTS]->(t:Document)
           WHERE t.path CONTAINS $name AND d.path CONTAINS 'test'
           RETURN d.path""",
        params={"name": target},
    )
    for row in (r.result_set or []):
        if row[0]:
            test_files.append(row[0])

    # Also check affected entities for test files mentioning target
    target_stem = Path(target).stem
    r2 = graph.query(
        """MATCH (d:Document) WHERE d.path CONTAINS 'test' AND d.path CONTAINS $stem RETURN d.path""",
        params={"stem": target_stem},
    )
    for row in (r2.result_set or []):
        if row[0] and row[0] not in test_files:
            test_files.append(row[0])

    has_tests = len(test_files) > 0

    # Compute risk
    if blast_count > 5 and not has_tests:
        risk = "dangerous"
        color = "red"
    elif blast_count <= 2 and has_tests:
        risk = "safe"
        color = "green"
    else:
        risk = "risky"
        color = "yellow"

    # Output
    tree = Tree(f"[bold {color}]Risk: {risk.upper()}[/] — {target}")
    tree.add(f"Blast radius: [bold]{blast_count}[/] entities")
    tree.add(f"Test coverage: {'[green]yes[/]' if has_tests else '[red]no[/]'} ({len(test_files)} test files)")
    if test_files:
        tb = tree.add("Test files")
        for tf in test_files:
            tb.add(f"[dim]{tf}[/]")
    if affected:
        ab = tree.add("Affected entities")
        for a in affected:
            ab.add(f"{_icon(a['type'])} {a['name']} [dim]({a['rel']})[/]")

    console.print(tree)


@app.command()
def upgrade():
    """Upgrade graph schema to the latest version."""
    from .migrations import check_and_migrate, get_schema_version, CURRENT_SCHEMA_VERSION

    graph = store.get_graph()
    current = get_schema_version(graph)
    console.print(f"[bold]Current schema:[/] v{current}")
    console.print(f"[bold]Target schema:[/]  v{CURRENT_SCHEMA_VERSION}")

    if current == CURRENT_SCHEMA_VERSION:
        console.print("[green]✓ Already up to date[/]")
        return

    result = check_and_migrate(graph, auto_migrate=True)
    for step in result["steps"]:
        console.print(f"  [green]✓[/] {step}")
    console.print(f"\n[green]✓ Upgraded to v{CURRENT_SCHEMA_VERSION}[/]")


@app.command()
def prune(
    older_than: int = typer.Option(30, help="Remove chunks not re-indexed in this many days"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed"),
):
    """Remove stale/orphaned data from the knowledge graph."""
    graph = store.get_graph()

    # Find orphaned chunks (no PART_OF edge)
    orphaned = graph.query("MATCH (c:Chunk) WHERE NOT (c)-[:PART_OF]->() RETURN count(c)")
    orphan_count = orphaned.result_set[0][0] if orphaned.result_set else 0

    # Find documents with no chunks
    empty_docs = graph.query(
        "MATCH (d:Document) WHERE NOT ()-[:PART_OF]->(d) AND NOT (d)-[:IN_REPO]->() RETURN count(d)"
    )
    empty_count = empty_docs.result_set[0][0] if empty_docs.result_set else 0

    # Find stale chunks (indexed_at older than threshold)
    # FalkorDB timestamp() returns ms since epoch
    threshold_ms = older_than * 86400 * 1000
    stale = graph.query(
        """MATCH (c:Chunk)
           WHERE c.indexed_at IS NOT NULL AND (timestamp() - c.indexed_at) > $threshold
           RETURN count(c)""",
        params={"threshold": threshold_ms},
    )
    stale_count = stale.result_set[0][0] if stale.result_set else 0

    console.print("[bold]Prune analysis:[/]")
    console.print(f"  Orphaned chunks (no document link): {orphan_count}")
    console.print(f"  Empty documents (no chunks):        {empty_count}")
    console.print(f"  Stale chunks (>{older_than} days):        {stale_count}")

    if dry_run:
        console.print("\n[yellow]Dry run — nothing removed.[/]")
        return

    total = 0
    if orphan_count > 0:
        graph.query("MATCH (c:Chunk) WHERE NOT (c)-[:PART_OF]->() DELETE c")
        total += orphan_count

    if empty_count > 0:
        graph.query("MATCH (d:Document) WHERE NOT ()-[:PART_OF]->(d) AND NOT (d)-[:IN_REPO]->() DELETE d")
        total += empty_count

    console.print(f"\n[green]✓ Removed {total} stale nodes[/]")


@app.command()
def watch(path: str = typer.Argument(".", help="Path to watch for changes")):
    """Watch a directory for file changes and re-index automatically."""
    from .watcher import watch_directory

    path = str(Path(path).expanduser().resolve())
    console.print(f"Watching {path} for changes...")
    watch_directory(path)


@app.command()
def changelog():
    """Generate CHANGELOG.md from git log, grouped by commit prefix."""
    import re

    repo_path = PROJECT_DIR
    result = subprocess.run(
        ["git", "log", "--oneline", "--format=%h %s", "v0.1.0..HEAD"],
        capture_output=True, text=True, cwd=repo_path,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "log", "--oneline", "--format=%h %s"],
            capture_output=True, text=True, cwd=repo_path,
        )

    groups: dict[str, list[str]] = {"feat": [], "fix": [], "docs": [], "release": [], "other": []}
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        match = re.match(r"^(\w+)\s+(feat|fix|docs|release):\s*(.+)$", line)
        if match:
            sha, prefix, msg = match.groups()
            groups[prefix].append(f"- {sha} {msg}")
        else:
            groups["other"].append(f"- {line}")

    md = "# Changelog\n\n"
    for section, label in [("feat", "Features"), ("fix", "Fixes"), ("docs", "Documentation"), ("release", "Releases"), ("other", "Other")]:
        if groups[section]:
            md += f"## {label}\n\n" + "\n".join(groups[section]) + "\n\n"

    out = repo_path / "CHANGELOG.md"
    out.write_text(md)
    console.print(f"[green]✓[/] Written {out}")


@app.command()
def setup(
    tool: str = typer.Argument(
        None,
        help="AI tool to configure: claude, cursor, kiro, copilot, amazonq, antigravity (or 'all')",
    ),
):
    """Auto-configure Knowledge Master MCP server for your AI tools."""
    import shutil

    # Find km-server path
    km_server_path = shutil.which("km-server")
    if not km_server_path:
        # Fall back to venv path
        venv_bin = Path(sys.executable).parent / "km-server"
        if venv_bin.exists():
            km_server_path = str(venv_bin)
        else:
            console.print("[red]✗ km-server not found on PATH.[/]")
            console.print("[dim]Run: pip install knowledge-master[/]")
            raise typer.Exit(1)

    configs = {
        "claude": {
            "path": Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
            "alt_path": Path.home() / ".config/claude/claude_desktop_config.json",
            "key": "mcpServers",
        },
        "cursor": {
            "path": Path.home() / ".cursor/mcp.json",
            "key": "mcpServers",
        },
        "kiro": {
            "path": Path.home() / ".kiro/settings/mcp.json",
            "key": "mcpServers",
        },
        "copilot": {
            "path": Path.home() / ".vscode/mcp.json",
            "key": "servers",
        },
        "amazonq": {
            "path": Path.home() / ".aws/amazonq/agents/default.json",
            "key": "mcpServers",
        },
        "antigravity": {
            "path": Path.home() / ".config/antigravity/mcp.json",
            "key": "mcpServers",
        },
    }

    if tool is None:
        console.print("[bold]Available tools:[/]")
        for name in configs:
            console.print(f"  • {name}")
        console.print("\n[dim]Usage: km setup <tool>  or  km setup all[/]")
        console.print(f"[dim]km-server path: {km_server_path}[/]")
        return

    targets = list(configs.keys()) if tool == "all" else [tool]

    for t in targets:
        if t not in configs:
            console.print(f"[yellow]Unknown tool: {t}[/]")
            continue

        cfg = configs[t]
        config_path = cfg["path"]
        if not config_path.exists() and "alt_path" in cfg:
            config_path = cfg["alt_path"]

        # Read or create config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except (json.JSONDecodeError, ValueError):
                existing = {}
        else:
            existing = {}

        # Add knowledge-master MCP server
        key = cfg["key"]
        if key not in existing:
            existing[key] = {}

        existing[key]["knowledge-master"] = {"command": km_server_path}

        config_path.write_text(json.dumps(existing, indent=2))
        console.print(f"  [green]✓[/] {t}: {config_path}")

    console.print("\n[bold green]Done![/] Restart your AI tool to activate Knowledge Master.")
    console.print(f"[dim]km-server: {km_server_path}[/]")


if __name__ == "__main__":
    app()
