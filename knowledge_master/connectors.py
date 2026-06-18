"""MCP Connector — index data from external MCP servers (email, Slack, etc.)."""

import asyncio
import json
from dataclasses import dataclass

from . import chunking, embeddings, store


@dataclass
class MCPSource:
    """Configuration for an external MCP server to pull data from."""
    name: str
    command: list[str]
    tool_name: str  # which tool to call to get data
    tool_args: dict  # arguments to pass
    source_type: str  # email, slack, docs, etc.


# Pre-configured sources — commands must be installed separately
SOURCES = {
    "outlook": MCPSource(
        name="Microsoft 365 Emails",
        command=["npx", "@subzone81/ms-365-mcp", "--preset", "mail"],
        tool_name="list-mail-messages",
        tool_args={"top": 50},
        source_type="email",
    ),
    "slack": MCPSource(
        name="Slack Messages",
        command=["npx", "@modelcontextprotocol/server-slack"],
        tool_name="slack_search_messages",
        tool_args={"query": ""},
        source_type="slack",
    ),
}


async def pull_and_index(source: MCPSource, graph=None):
    """Connect to an MCP server, pull data, and index it into our graph."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    if graph is None:
        graph = store.get_graph()
    store.init_schema(graph)

    params = StdioServerParameters(command=source.command[0], args=source.command[1:])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Call the tool to get data
            result = await session.call_tool(source.tool_name, source.tool_args)

            items = _parse_mcp_result(result)
            indexed = 0

            for item in items:
                text = item.get("text", item.get("content", item.get("body", "")))
                if not text or len(text.strip()) < 20:
                    continue

                title = item.get("subject", item.get("title", item.get("name", "")))
                author = item.get("from", item.get("author", item.get("user", "")))
                source_id = item.get("id", item.get("url", title))

                # Chunk and embed
                chunks = chunking.chunk_text(text)
                vectors = embeddings.embed_batch(chunks)

                # Store document
                doc_path = f"{source.source_type}/{source_id}"
                store.upsert_document(graph, doc_path, source.source_type, {"title": title})

                # Store person if we have author info
                if author:
                    email = author if "@" in author else ""
                    store.upsert_person(graph, author, email)
                    store.link_person_authored(graph, email or author, doc_path)

                # Store chunks
                for i, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                    cid = chunking.chunk_id(doc_path, i)
                    store.upsert_chunk(graph, cid, chunk_text, vector,
                                       {"source": doc_path, "source_type": source.source_type})
                    store.link_chunk_to_document(graph, cid, doc_path)

                indexed += 1

    return {"source": source.name, "items_indexed": indexed}


def _parse_mcp_result(result) -> list[dict]:
    """Parse MCP tool result into a list of items."""
    items = []
    for content in result.content:
        if hasattr(content, "text"):
            try:
                data = json.loads(content.text)
                if isinstance(data, list):
                    items.extend(data)
                elif isinstance(data, dict):
                    if "results" in data:
                        items.extend(data["results"])
                    elif "messages" in data:
                        items.extend(data["messages"])
                    elif "items" in data:
                        items.extend(data["items"])
                    else:
                        items.append(data)
            except json.JSONDecodeError:
                # Plain text — treat as single item
                items.append({"text": content.text, "title": "mcp-result"})
    return items


def sync_pull_and_index(source_key: str, graph=None):
    """Synchronous wrapper for CLI usage."""
    if source_key not in SOURCES:
        available = ", ".join(SOURCES.keys())
        raise ValueError(f"Unknown source: {source_key}. Available: {available}")
    source = SOURCES[source_key]
    return asyncio.run(pull_and_index(source, graph))


def add_custom_source(name: str, command: list[str], tool_name: str,
                      tool_args: dict = None, source_type: str = "external"):
    """Register a custom MCP source."""
    SOURCES[name] = MCPSource(
        name=name, command=command, tool_name=tool_name,
        tool_args=tool_args or {}, source_type=source_type,
    )
