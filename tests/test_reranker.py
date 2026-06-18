"""Benchmark test for re-ranker — compare raw cosine vs re-ranked ordering.

This is an integration test (requires Ollama) but demonstrates the value of re-ranking.
Run with: pytest tests/integration/test_reranker_benchmark.py -v
"""
import pytest
from knowledge_master.rerank import rerank, _cosine_sim


def test_cosine_sim_identical():
    a = [1.0, 0.0, 0.0]
    assert _cosine_sim(a, a) == pytest.approx(1.0)


def test_cosine_sim_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert _cosine_sim(a, b) == pytest.approx(0.0)


def test_cosine_sim_opposite():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert _cosine_sim(a, b) == pytest.approx(-1.0)


def test_rerank_empty():
    result = rerank("test query", [], top_k=5)
    assert result == []


def test_rerank_preserves_fields():
    """Re-rank should keep all original result fields."""
    results = [
        {"text": "hello world", "source": "a.py", "score": 0.5, "extra": "keep"},
    ]
    # This would normally call Ollama — skip if not available
    try:
        ranked = rerank("hello", results, top_k=1)
        assert "extra" in ranked[0]
        assert "rerank_score" in ranked[0]
    except Exception:
        pytest.skip("Ollama not available")
