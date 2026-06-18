"""Unit tests for API endpoints with mocked dependencies."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from knowledge_master.web import create_app


@patch("knowledge_master.api.store")
@patch("knowledge_master.api.embeddings")
def test_search_endpoint(mock_embeddings, mock_store):
    mock_embeddings.embed.return_value = [0.0] * 768
    mock_store.get_graph.return_value = MagicMock()
    mock_store.graph_context_search.return_value = [
        {"text": "hello", "score": 0.9, "source": "test.py"}
    ]

    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/search", params={"q": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "results" in data


@patch("knowledge_master.api.store")
def test_blast_radius_endpoint(mock_store):
    mock_graph = MagicMock()
    mock_store.get_graph.return_value = mock_graph
    mock_result = MagicMock()
    mock_result.result_set = [("Repo", "my-repo")]
    mock_graph.query.return_value = mock_result

    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/blast-radius/Python")
    assert resp.status_code == 200
    data = resp.json()
    assert "target" in data
    assert "affected" in data
