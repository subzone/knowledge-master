"""Integration tests — require FalkorDB and Ollama running."""
import pytest
from knowledge_master import embeddings, store


@pytest.fixture
def graph():
    g = store.get_graph()
    store.init_schema(g)
    return g


def test_embedding_dimensions():
    vec = embeddings.embed("test query")
    assert len(vec) == 768
    assert all(isinstance(v, float) for v in vec)


def test_store_upsert_and_search(graph):
    vec = embeddings.embed("kubernetes deployment configuration")
    store.upsert_chunk(graph, "test-1", "kubernetes deployment config", vec,
                       {"source": "test.yaml", "source_type": "infra"})

    results = store.vector_search(graph, vec, top_k=1)
    assert len(results) >= 1
    assert results[0]["id"] == "test-1"


def test_graph_relationships(graph):
    store.upsert_repo(graph, "test-repo", "/tmp/test")
    store.upsert_person(graph, "Test User", "test@example.com")
    store.upsert_document(graph, "main.py", "py", {"title": "main"})
    store.link_document_to_repo(graph, "main.py", "test-repo")
    store.link_person_authored(graph, "test@example.com", "main.py")

    stats = store.get_stats(graph)
    assert stats["repos"] >= 1
    assert stats["documents"] >= 1
