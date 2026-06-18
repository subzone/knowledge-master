"""CLI for knowledge-master — simple commands for indexing, searching, and managing."""

import json
import subprocess
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
    compose_file = PROJECT_DIR / "docker-compose.yml"

    console.print("[bold]Starting Knowledge Master...[/]\n")

    # Check Docker
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[red]✗ Docker is not running.[/] Please start Docker first.")
        raise typer.Exit(1)

    # Start containers
    console.print("  [dim]Starting FalkorDB + Postgres...[/]")
    result = subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d"],
                            capture_output=True, text=True)
    if result.returncode != 0 and "error" in result.stderr.lower():
        console.print(f"[red]✗ Docker Compose failed:[/] {result.stderr.strip()}")
        raise typer.Exit(1)
    # Wait for healthy
    subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "--wait"],
                   capture_output=True)
    console.print("  [green]✓[/] Containers running")

    # Check/pull Ollama model
    console.print("  [dim]Checking embedding model...[/]")
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "nomic-embed-text" not in result.stdout:
            console.print("  [dim]Pulling nomic-embed-text...[/]")
            subprocess.run(["ollama", "pull", "nomic-embed-text"], check=True)
        console.print("  [green]✓[/] Embedding model ready")
    except FileNotFoundError:
        console.print("[red]✗ Ollama not found.[/] Install from https://ollama.com")
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
    compose_file = PROJECT_DIR / "docker-compose.yml"
    subprocess.run(["docker", "compose", "-f", str(compose_file), "down"], capture_output=True)
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
    results = store.graph_context_search(graph, vec, top_k)

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
    target: str = typer.Argument(..., help="Service, file, or tech name to check"),
    depth: int = typer.Option(3, "--depth", "-d", help="Traversal depth"),
):
    """Show what depends on a target — the blast radius of changing it."""
    graph = store.get_graph()

    # Try as Service first
    result = graph.query(
        """MATCH (target:Service {name: $name})
           OPTIONAL MATCH path = (other)-[*1..3]->(target)
           WHERE other <> target
           RETURN labels(other)[0] AS type, other.name AS name,
                  length(path) AS distance, type(last(relationships(path))) AS rel
           ORDER BY distance""",
        params={"name": target},
    )

    if not result.result_set:
        # Try as Tech
        result = graph.query(
            """MATCH (target:Tech {name: $name})
               OPTIONAL MATCH (r:Repo)-[:USES_TECH]->(target)
               RETURN 'Repo' AS type, r.name AS name, 1 AS distance, 'USES_TECH' AS rel""",
            params={"name": target},
        )

    if not result.result_set:
        # Try as file/document
        result = graph.query(
            """MATCH (target:Document) WHERE target.path CONTAINS $name
               OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(target)
               OPTIONAL MATCH (p:Person)-[:AUTHORED]->(target)
               OPTIONAL MATCH (target)-[:IN_REPO]->(r:Repo)
               RETURN 'Repo' AS type, r.name AS name, 1 AS distance, 'CONTAINS' AS rel
               UNION
               MATCH (target:Document) WHERE target.path CONTAINS $name
               OPTIONAL MATCH (p:Person)-[:AUTHORED]->(target)
               RETURN 'Person' AS type, p.name AS name, 1 AS distance, 'AUTHORED' AS rel""",
            params={"name": target},
        )

    if not result.result_set or all(r[1] is None for r in result.result_set):
        console.print(f"[yellow]No dependencies found for:[/] {target}")
        console.print("[dim]Try: a service name, technology, or file path[/]")
        return

    tree = Tree(f"[bold red]💥 Blast radius: {target}[/]")
    seen = set()
    for node_type, name, distance, rel in result.result_set:
        if name and name not in seen:
            seen.add(name)
            icon = {"Repo": "📦", "Service": "⚙️", "Person": "👤", "Document": "📄", "Tech": "🔧"}.get(node_type, "•")
            tree.add(f"{icon} [bold]{name}[/] [dim]({node_type}, via {rel})[/]")

    console.print(tree)
    console.print(f"\n[dim]{len(seen)} entities affected[/]")


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


if __name__ == "__main__":
    app()
