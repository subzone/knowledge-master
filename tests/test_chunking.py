"""Unit tests — no external services required."""
from knowledge_master import chunking


def test_chunk_markdown():
    text = "# Title\n\nParagraph one.\n\n## Section\n\nParagraph two."
    chunks = chunking.chunk_markdown(text)
    assert len(chunks) >= 2
    assert "Title" in chunks[0]


def test_chunk_code_python():
    text = "def foo():\n    pass\n\ndef bar():\n    return 1\n"
    chunks = chunking.chunk_code(text, "python")
    assert len(chunks) >= 1


def test_chunk_file_routes_by_extension():
    text = "# Hello\n\nWorld"
    chunks = chunking.chunk_file(text, ".md")
    assert len(chunks) >= 1


def test_chunk_id_deterministic():
    id1 = chunking.chunk_id("file.py", 0)
    id2 = chunking.chunk_id("file.py", 0)
    id3 = chunking.chunk_id("file.py", 1)
    assert id1 == id2
    assert id1 != id3


def test_chunk_file_empty_input():
    """Empty input should return empty list."""
    chunks = chunking.chunk_file("", ".py")
    assert chunks == []


def test_chunk_file_very_long():
    """Very long file should still produce chunks."""
    text = "def fn_{i}():\n    pass\n\n".replace("{i}", "x") * 500
    chunks = chunking.chunk_file(text, ".py")
    assert len(chunks) >= 1


def test_chunk_file_unknown_extension():
    """Unknown extension falls back to text chunking."""
    text = "Some content\n\nAnother paragraph"
    chunks = chunking.chunk_file(text, ".xyz")
    assert len(chunks) >= 1
