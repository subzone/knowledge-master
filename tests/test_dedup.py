"""Tests for store deduplication and content hashing."""
from knowledge_master.store import content_hash


def test_content_hash_deterministic():
    h1 = content_hash("hello world")
    h2 = content_hash("hello world")
    assert h1 == h2


def test_content_hash_different_for_different_content():
    h1 = content_hash("hello world")
    h2 = content_hash("hello world!")
    assert h1 != h2


def test_content_hash_length():
    h = content_hash("test")
    assert len(h) == 16  # sha256 truncated to 16 chars


def test_content_hash_hex():
    h = content_hash("test")
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_empty_string():
    """Empty string should still produce a valid hash."""
    h = content_hash("")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
