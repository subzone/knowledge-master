"""REST API — JSON endpoints for external tool integration."""

from pathlib import Path

from fastapi import APIRouter

from . import embeddings, store
from .parsers import git_repo, markdown

router = APIRouter(prefix="/api/v1")


@router.get("/search")
async def search(q: str, top_k: int = 10, source_type: str = None):
    """Semantic search across the knowledge base."""
    graph = store.get_graph()
    vec = embeddings.embed(q)
    results = store.graph_context_search(graph, vec, top_k, query=q)
    if source_type:
        results = [r for r in results if r.get("source_type") == source_type]
    return {"query": q, "results": results}


@router.get("/blast-radius/{target}")
async def blast_radius(target: str):
    """Show what depends on a target."""
    graph = store.get_graph()
    # Try Service
    result = graph.query(
        """MATCH (t:Service {name: $name})
           OPTIONAL MATCH (other)-[*1..3]->(t)
           WHERE other <> t
           RETURN labels(other)[0] AS type, other.name AS name""",
        params={"name": target},
    )
    if not result.result_set or all(r[1] is None for r in result.result_set):
        # Try Tech
        result = graph.query(
            """MATCH (t:Tech {name: $name})
               OPTIONAL MATCH (r:Repo)-[:USES_TECH]->(t)
               RETURN 'Repo' AS type, r.name AS name""",
            params={"name": target},
        )
    affected = [{"type": r[0], "name": r[1]} for r in (result.result_set or []) if r[1]]
    return {"target": target, "affected_count": len(affected), "affected": affected}


@router.get("/conventions/check")
async def check_conventions(path: str = "."):
    """Check conventions for a path."""
    path = str(Path(path).expanduser().resolve())
    repo_name = Path(path).name
    graph = store.get_graph()

    result = graph.query(
        "MATCH (r:Repo)-[:FOLLOWS]->(c:Convention) WHERE r.name = $name RETURN c.name, c.category",
        params={"name": repo_name},
    )
    if not result.result_set:
        result = graph.query("MATCH (c:Convention) RETURN c.name, c.category")

    from .cli import _check_convention
    checks = []
    for conv_name, category in (result.result_set or []):
        passed = _check_convention(path, conv_name)
        checks.append({"convention": conv_name, "category": category, "passed": passed})
    return {"path": path, "checks": checks}


@router.post("/index")
async def index_source(path: str, type: str = "auto"):
    """Index a repo or directory."""
    path = str(Path(path).expanduser().resolve())
    if not Path(path).exists():
        return {"error": f"Path not found: {path}"}

    graph = store.get_graph()
    store.init_schema(graph)
    resolved_type = type if type != "auto" else ("repo" if (Path(path) / ".git").exists() else "docs")

    if resolved_type == "repo":
        result = git_repo.index_repo(path, graph)
    else:
        result = markdown.index_directory(path, graph)
    return result


@router.get("/status")
async def status():
    """Knowledge base stats."""
    graph = store.get_graph()
    return store.get_stats(graph)
