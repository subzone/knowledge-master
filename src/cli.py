"""CLI for knowledge-master - manual ingest and search."""

import json

import typer
from rich.console import Console
from rich.table import Table

from . import embeddings, store
from .parsers import git_repo, markdown

app = typer.Typer(name="km", help="Knowledge Master - local RAG knowledge base")
console = Console()


@app.command()
def index_repo(path: str, branch: str = "HEAD"):
    """Index a git repository."""
    console.print(f"[bold]Indexing repo:[/] {path}")
    graph = store.get_graph()
    store.init_schema(graph)
    result = git_repo.index_repo(path, graph, branch)
    console.print(f"[green]Done![/] {result}")


@app.command()
def index_dir(path: str, patterns: list[str] = None):
    """Index a directory of documents."""
    console.print(f"[bold]Indexing directory:[/] {path}")
    graph = store.get_graph()
    store.init_schema(graph)
    result = markdown.index_directory(path, graph, patterns)
    console.print(f"[green]Done![/] {result}")


@app.command()
def search(query: str, top_k: int = 10, graph_context: bool = True):
    """Semantic search across the knowledge base."""
    graph = store.get_graph()
    query_vector = embeddings.embed(query)

    if graph_context:
        results = store.graph_context_search(graph, query_vector, top_k)
    else:
        results = store.vector_search(graph, query_vector, top_k)

    table = Table(title=f"Results for: {query}")
    table.add_column("Score", width=6)
    table.add_column("Source", width=40)
    table.add_column("Text", width=80)
    table.add_column("Context", width=30)

    for r in results:
        context = ""
        if graph_context:
            parts = []
            if r.get("repo"):
                parts.append(f"repo:{r['repo']}")
            if r.get("author"):
                parts.append(f"by:{r['author']}")
            context = ", ".join(parts)

        table.add_row(
            f"{r.get('score', 0):.3f}",
            r.get("source", r.get("doc_path", "")),
            r.get("text", "")[:120] + "...",
            context,
        )

    console.print(table)


@app.command()
def status():
    """Show knowledge base statistics."""
    graph = store.get_graph()
    stats = store.get_stats(graph)
    console.print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    app()
