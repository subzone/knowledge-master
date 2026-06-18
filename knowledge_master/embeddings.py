"""Embedding client using Ollama local models."""

import ollama

MODEL = "nomic-embed-text"
TIMEOUT = 30  # seconds per request


def embed(text: str) -> list[float]:
    """Embed a single text string, returns vector."""
    response = ollama.embed(model=MODEL, input=text, request_timeout=TIMEOUT)
    return response["embeddings"][0]


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed multiple texts in batches."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = ollama.embed(model=MODEL, input=batch, request_timeout=TIMEOUT)
        vectors.extend(response["embeddings"])
    return vectors
