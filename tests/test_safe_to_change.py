"""Tests for safe-to-change risk scoring logic."""

from unittest.mock import MagicMock, patch

from knowledge_master.cli import _compute_blast_radius


def _mock_graph(import_results=None, function_results=None, service_results=None,
                service_dep_results=None, tech_results=None, person_results=None,
                cross_repo_results=None):
    """Create a mock graph that returns specified results for each query layer."""
    graph = MagicMock()
    responses = iter([
        MagicMock(result_set=import_results or []),
        MagicMock(result_set=function_results or []),
        MagicMock(result_set=service_results or []),
        MagicMock(result_set=service_dep_results or []),
        MagicMock(result_set=tech_results or []),
        MagicMock(result_set=person_results or []),
        MagicMock(result_set=cross_repo_results or []),
    ])
    graph.query.side_effect = lambda *a, **kw: next(responses)
    return graph


def test_risk_safe_when_few_entities():
    """<=2 entities means low blast radius."""
    graph = _mock_graph(
        import_results=[("Document", "a.py", "IMPORTS"), ("Document", "b.py", "IMPORTS")],
    )
    results = _compute_blast_radius(graph, "target.py")
    assert len(results) <= 2


def test_risk_dangerous_when_many_entities():
    """>5 entities means high blast radius."""
    graph = _mock_graph(
        import_results=[
            ("Document", "a.py", "IMPORTS"),
            ("Document", "b.py", "IMPORTS"),
            ("Document", "c.py", "IMPORTS"),
        ],
        function_results=[
            ("Document", "d.py", "IMPORTS function"),
            ("Document", "e.py", "IMPORTS function"),
            ("Document", "f.py", "IMPORTS function"),
        ],
    )
    results = _compute_blast_radius(graph, "target.py")
    assert len(results) > 5


def test_blast_radius_empty_graph():
    """Empty graph returns no affected entities."""
    graph = _mock_graph()
    results = _compute_blast_radius(graph, "nonexistent")
    assert results == []
