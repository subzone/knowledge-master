"""Embedding client using Ollama local models."""

import os

from ollama import Client

MODEL = os.environ.get("KM_EMBED_MODEL", "nomic-embed-text")
TIMEOUT = 30

_client = Client(
    host=os.environ.get("KM_OLLAMA_HOST", "http://localhost:11434"),
    timeout=TIMEOUT,
)


def embed(text: str) -> list[float]:
    """Embed a single text string, returns vector."""
    response = _client.embed(model=MODEL, input=text)
    return response["embeddings"][0]


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed multiple texts in batches."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = _client.embed(model=MODEL, input=batch)
        vectors.extend(response["embeddings"])
    return vectors
