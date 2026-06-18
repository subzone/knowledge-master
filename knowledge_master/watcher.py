"""Incremental indexing — git hook and file watcher support."""

import os
import subprocess
import sys
from pathlib import Path

from . import chunking, embeddings, store
from .parsers.git_repo import _index_file, _should_index, INDEXABLE_EXTENSIONS

from git import Repo


def index_changed_files(repo_path: str, since: str = "HEAD~1"):
    """Index only files that changed since a given ref."""
    repo_path = str(Path(repo_path).expanduser().resolve())
    repo = Repo(repo_path)
    repo_name = Path(repo_path).name
    graph = store.get_graph()
    store.init_schema(graph)
    store.upsert_repo(graph, repo_name, repo_path)

    # Get changed files
    try:
        diff_output = repo.git.diff("--name-only", since)
        changed = [f for f in diff_output.splitlines() if _should_index(f)]
    except Exception:
        changed = []

    indexed = 0
    for filepath in changed:
        full_path = os.path.join(repo_path, filepath)
        if os.path.exists(full_path):
            try:
                _index_file(graph, full_path, filepath, repo_name, repo)
                indexed += 1
            except Exception:
                pass
        else:
            # File was deleted — remove its chunks
            graph.query(
                """MATCH (d:Document {path: $path})
                   OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(d)
                   DELETE c, d""",
                params={"path": filepath},
            )

    return {"repo": repo_name, "changed": len(changed), "indexed": indexed}


def install_git_hook(repo_path: str):
    """Install a post-commit git hook that triggers incremental indexing."""
    repo_path = str(Path(repo_path).expanduser().resolve())
    hook_dir = Path(repo_path) / ".git" / "hooks"
    hook_file = hook_dir / "post-commit"

    # Find km executable
    km_bin = Path(sys.executable).parent / "km"
    if not km_bin.exists():
        km_bin = f"{sys.executable} -m knowledge_master.cli"

    hook_content = f"""#!/bin/sh
# Knowledge Master — auto-index on commit
{km_bin} index {repo_path} --type repo 2>/dev/null &
"""

    hook_file.write_text(hook_content)
    hook_file.chmod(0o755)
    return str(hook_file)


def watch_directory(path: str, callback=None):
    """Watch a directory for changes and re-index (uses polling for cross-platform)."""
    import time
    path = str(Path(path).expanduser().resolve())
    last_mtimes = {}

    def scan():
        current = {}
        for ext in INDEXABLE_EXTENSIONS:
            for f in Path(path).rglob(f"*{ext}"):
                if ".git" in f.parts or ".venv" in f.parts:
                    continue
                current[str(f)] = f.stat().st_mtime
        return current

    last_mtimes = scan()
    print(f"Watching {path} for changes... (Ctrl+C to stop)")

    while True:
        time.sleep(2)
        current = scan()
        changed = [f for f, mtime in current.items() if last_mtimes.get(f) != mtime]
        deleted = [f for f in last_mtimes if f not in current]

        if changed or deleted:
            if callback:
                callback(changed, deleted)
            else:
                print(f"  Changed: {len(changed)}, Deleted: {len(deleted)}")
                if (Path(path) / ".git").exists():
                    result = index_changed_files(path, "HEAD~1")
                    print(f"  Indexed: {result}")

        last_mtimes = current
