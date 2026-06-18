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
            results = store.graph_context_search(graph, query_vector, top_k)
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

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
