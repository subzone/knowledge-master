"""MCP Server exposing knowledge base tools for AI agents."""

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import embeddings, store
from .parsers import git_repo, markdown

server = Server("knowledge-master")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search",
            description="Semantic search across the knowledge base. Returns relevant chunks with source info and graph context (author, repo, related docs).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "top_k": {"type": "integer", "default": 10, "description": "Number of results"},
                    "source_type": {"type": "string", "enum": ["code", "docs", "email", "infra"], "description": "Filter by source type"},
                    "use_graph": {"type": "boolean", "default": True, "description": "Include graph context (author, repo relationships)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="index_repo",
            description="Index a git repository into the knowledge graph. Parses code files, extracts authors, builds relationships.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to git repository"},
                    "branch": {"type": "string", "default": "HEAD", "description": "Branch to index"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="index_directory",
            description="Index markdown/text files from a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to index"},
                    "patterns": {"type": "array", "items": {"type": "string"}, "description": "Glob patterns (default: *.md, *.txt)"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="get_status",
            description="Get knowledge base statistics: number of chunks, documents, repos indexed.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="blast_radius",
            description="Show what depends on a target (service, tech, or file). Returns all entities that would be affected by changing the target.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Service name, technology, or file to check dependencies for"},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="check_conventions",
            description="Check if a repo or path follows the detected coding conventions (naming, structure, patterns). Returns pass/fail for each convention.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to repo or directory to check"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="safe_to_change",
            description="Assess risk of changing a target. Returns risk level, blast radius, and test coverage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "File or module to assess"},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="who_owns",
            description="Find who owns a file based on OWNS relationships in the graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "File path to check ownership"},
                },
                "required": ["file"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    graph = store.get_graph()

    if name == "search":
        query = arguments["query"]
        top_k = arguments.get("top_k", 10)
        use_graph = arguments.get("use_graph", True)
        filters = {}
        if arguments.get("source_type"):
            filters["source_type"] = arguments["source_type"]

        query_vector = embeddings.embed(query)

        if use_graph:
            results = store.graph_context_search(graph, query_vector, top_k, query=query)
        else:
            results = store.vector_search(graph, query_vector, top_k, filters)

        return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

    elif name == "index_repo":
        result = git_repo.index_repo(arguments["path"], graph, arguments.get("branch", "HEAD"))
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "index_directory":
        result = markdown.index_directory(
            arguments["path"], graph, arguments.get("patterns")
        )
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "get_status":
        stats = store.get_stats(graph)
        return [TextContent(type="text", text=json.dumps(stats))]

    elif name == "blast_radius":
        target = arguments["target"]
        # Try Service
        result = graph.query(
            """MATCH (t:Service {name: $name})
               OPTIONAL MATCH (other)-[*1..3]->(t)
               WHERE other <> t
               RETURN labels(other)[0] AS type, other.name AS name, type(last(relationships(path))) AS rel""",
            params={"name": target},
        )
        if not result.result_set or all(r[1] is None for r in result.result_set):
            # Try Tech
            result = graph.query(
                """MATCH (t:Tech {name: $name})
                   OPTIONAL MATCH (r:Repo)-[:USES_TECH]->(t)
                   RETURN 'Repo' AS type, r.name AS name, 'USES_TECH' AS rel""",
                params={"name": target},
            )
        affected = [{"type": r[0], "name": r[1], "relationship": r[2]}
                    for r in (result.result_set or []) if r[1]]
        output = {"target": target, "affected_count": len(affected), "affected": affected}
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    elif name == "check_conventions":
        from pathlib import Path as P
        path = str(P(arguments["path"]).expanduser().resolve())
        repo_name = P(path).name
        result = graph.query(
            """MATCH (r:Repo)-[:FOLLOWS]->(c:Convention)
               WHERE r.name = $name
               RETURN c.name, c.category""",
            params={"name": repo_name},
        )
        if not result.result_set:
            result = graph.query("MATCH (c:Convention) RETURN c.name, c.category")

        checks = []
        for conv_name, category in (result.result_set or []):
            passed = _check_convention_simple(path, conv_name)
            checks.append({"convention": conv_name, "category": category, "passed": passed})

        return [TextContent(type="text", text=json.dumps({"path": path, "checks": checks}, indent=2))]

    elif name == "safe_to_change":
        from .cli import _compute_blast_radius
        from pathlib import Path as P
        target = arguments["target"]
        affected = _compute_blast_radius(graph, target)
        blast_count = len(affected)

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
        target_stem = P(target).stem
        r2 = graph.query(
            """MATCH (d:Document) WHERE d.path CONTAINS 'test' AND d.path CONTAINS $stem RETURN d.path""",
            params={"stem": target_stem},
        )
        for row in (r2.result_set or []):
            if row[0] and row[0] not in test_files:
                test_files.append(row[0])

        has_tests = len(test_files) > 0
        if blast_count > 5 and not has_tests:
            risk = "dangerous"
        elif blast_count <= 2 and has_tests:
            risk = "safe"
        else:
            risk = "risky"

        output = {
            "target": target,
            "risk": risk,
            "blast_radius": blast_count,
            "has_tests": has_tests,
            "test_files": test_files,
            "affected": [{"type": a["type"], "name": a["name"]} for a in affected],
        }
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    elif name == "who_owns":
        file = arguments["file"]
        result = graph.query(
            """MATCH (p:Person)-[r:OWNS]->(d:Document)
               WHERE d.path CONTAINS $file
               RETURN p.name, r.weight, d.path
               ORDER BY r.weight DESC LIMIT 1""",
            params={"file": file},
        )
        if result.result_set:
            owner_name, weight, path = result.result_set[0]
            output = {"file": path, "owner": owner_name, "weight": float(weight)}
        else:
            output = {"file": file, "owner": None, "weight": 0.0}
        return [TextContent(type="text", text=json.dumps(output, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _check_convention_simple(path: str, convention: str) -> bool:
    """Check a single convention."""
    from pathlib import Path as P
    p = P(path)
    if convention == "src/ directory":
        return (p / "src").is_dir()
    elif convention == "separate test directory":
        return (p / "tests").is_dir() or (p / "test").is_dir()
    elif convention == "docs/ directory":
        return (p / "docs").is_dir()
    elif convention == "snake_case files":
        files = [f for f in p.rglob("*.py") if ".venv" not in str(f)]
        return not any("-" in f.stem for f in files)
    return True


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
