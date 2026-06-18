"""Markdown file/directory parser."""

import os
from pathlib import Path

from rich.progress import Progress

from .. import chunking, embeddings, store


def index_directory(directory: str, graph=None, patterns: list[str] = None):
    """Index markdown files from a directory."""
    directory = os.path.expanduser(directory)
    if graph is None:
        graph = store.get_graph()

    store.init_schema(graph)
    patterns = patterns or ["*.md", "*.markdown", "*.txt"]

    files = []
    for pattern in patterns:
        files.extend(Path(directory).rglob(pattern))

    with Progress() as progress:
        task = progress.add_task(f"Indexing {directory}", total=len(files))
        for filepath in files:
            try:
                _index_markdown(graph, str(filepath), directory)
            except Exception as e:
                progress.console.print(f"  [yellow]skip {filepath}: {e}[/]")
            progress.advance(task)

    return {"directory": directory, "files_indexed": len(files)}


def _index_markdown(graph, filepath: str, base_dir: str):
    """Index a single markdown file."""
    with open(filepath, "r", errors="ignore") as f:
        content = f.read()

    if not content.strip():
        return

    relative = os.path.relpath(filepath, base_dir)
    chunks = chunking.chunk_markdown(content)
    if not chunks:
        return

    vectors = embeddings.embed_batch(chunks)
    store.upsert_document(graph, relative, "markdown", {"title": relative})

    for i, (text, vector) in enumerate(zip(chunks, vectors)):
        cid = chunking.chunk_id(relative, i)
        store.upsert_chunk(
            graph, cid, text, vector, {"source": relative, "source_type": "docs"}
        )
        store.link_chunk_to_document(graph, cid, relative)
