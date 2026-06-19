"""Tests for ownership extraction logic."""

import os
import subprocess
import tempfile

from unittest.mock import MagicMock, patch

from knowledge_master.parsers.git_repo import index_repo


@patch("knowledge_master.parsers.git_repo.embeddings")
@patch("knowledge_master.parsers.git_repo.store")
@patch("knowledge_master.parsers.git_repo.extract_all")
@patch("knowledge_master.parsers.git_repo.build_import_graph_all")
def test_extract_ownership_creates_owns_edges(mock_static, mock_intel, mock_store, mock_embed):
    """Index a temp git repo and verify upsert_person is called with author info."""
    mock_embed.embed_batch.return_value = [[0.0] * 768]
    mock_graph = MagicMock()
    mock_store.get_graph.return_value = mock_graph
    mock_intel.return_value = {}
    mock_static.return_value = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a git repo with one commit
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "dev@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Dev"], cwd=tmpdir, capture_output=True)
        filepath = os.path.join(tmpdir, "hello.py")
        with open(filepath, "w") as f:
            f.write("def hello():\n    pass\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)

        index_repo(tmpdir, mock_graph)

    # Verify person was upserted
    mock_store.upsert_person.assert_called()
    call_args = mock_store.upsert_person.call_args_list[0]
    assert call_args[0][1] == "Dev"
    assert call_args[0][2] == "dev@test.com"


@patch("knowledge_master.parsers.git_repo.embeddings")
@patch("knowledge_master.parsers.git_repo.store")
@patch("knowledge_master.parsers.git_repo.extract_all")
@patch("knowledge_master.parsers.git_repo.build_import_graph_all")
def test_index_repo_links_author_to_file(mock_static, mock_intel, mock_store, mock_embed):
    """Verify link_person_authored is called for committed files."""
    mock_embed.embed_batch.return_value = [[0.0] * 768]
    mock_graph = MagicMock()
    mock_store.get_graph.return_value = mock_graph
    mock_intel.return_value = {}
    mock_static.return_value = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "author@example.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Author"], cwd=tmpdir, capture_output=True)
        filepath = os.path.join(tmpdir, "main.py")
        with open(filepath, "w") as f:
            f.write("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add main"], cwd=tmpdir, capture_output=True)

        index_repo(tmpdir, mock_graph)

    mock_store.link_person_authored.assert_called()
