"""Tests for web UI endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from knowledge_master.web import create_app


def _client():
    app = create_app()
    return TestClient(app)


def test_home_page():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Knowledge Master" in resp.text


def test_graph_page():
    client = _client()
    resp = client.get("/graph")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Knowledge Graph" in resp.text


@patch("knowledge_master.web.store")
def test_browse_restricted_to_home(mock_store):
    client = _client()
    resp = client.get("/api/browse", params={"path": "/etc"})
    assert resp.status_code == 200
    data = resp.json()
    # Should redirect to home, not serve /etc
    import os
    home = os.path.expanduser("~")
    assert data["current"].startswith(home)


@patch("knowledge_master.web.store")
def test_stats_endpoint(mock_store):
    mock_graph = MagicMock()
    mock_store.get_graph.return_value = mock_graph
    mock_store.get_stats.return_value = {"chunks": 42, "documents": 5, "repos": 2}
    client = _client()
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    assert "chunks" in resp.text
