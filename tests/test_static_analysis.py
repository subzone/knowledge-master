"""Unit tests for static_analysis module."""

import os
import tempfile

from knowledge_master.static_analysis import extract_python_graph, resolve_import


def test_extract_python_graph(tmp_path):
    code = """\
import os
from pathlib import Path

def hello():
    pass

class Greeter:
    pass
"""
    f = tmp_path / "sample.py"
    f.write_text(code)
    result = extract_python_graph(str(f))

    assert result["path"] == str(f)
    # Imports
    modules = [i["module"] for i in result["imports"]]
    assert "os" in modules
    assert "pathlib" in modules
    # Exports
    names = [e["name"] for e in result["exports"]]
    assert "hello" in names
    assert "Greeter" in names
    assert any(e["type"] == "function" for e in result["exports"])
    assert any(e["type"] == "class" for e in result["exports"])


def test_resolve_import(tmp_path):
    # Create a package structure: pkg/a.py imports from pkg/b.py
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "b.py").write_text("x = 1\n")
    (pkg / "a.py").write_text("from . import b\n")

    # Relative import (level=1, module='b') from pkg/a.py
    resolved = resolve_import("b", level=1, source_file="pkg/a.py", repo_root=str(tmp_path))
    assert resolved is not None
    assert resolved.endswith("b.py")


def test_extract_python_graph_syntax_error(tmp_path):
    """Syntax errors should not crash the extractor."""
    code = "def broken(\n    return ===\n"
    f = tmp_path / "bad.py"
    f.write_text(code)
    result = extract_python_graph(str(f))
    # Should return a result dict without crashing
    assert isinstance(result, dict)
    assert result["path"] == str(f)
