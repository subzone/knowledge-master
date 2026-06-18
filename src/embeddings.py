"""Embedding client using Ollama local models."""

import ollama

MODEL = "nomic-embed-text"


def embed(text: str) -> list[float]:
    """Embed a single text string, returns vector."""
    response = ollama.embed(model=MODEL, input=text)
    return response["embeddings"][0]


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed multiple texts in batches."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = ollama.embed(model=MODEL, input=batch)
        vectors.extend(response["embeddings"])
    return vectors
