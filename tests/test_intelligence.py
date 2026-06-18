"""Unit tests for intelligence extraction (no DB required)."""
import tempfile
import os
from pathlib import Path


def test_convention_detection_src_dir():
    """Test that src/ directory convention is detected."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "src").mkdir()
        # Import here to avoid needing FalkorDB for collection
        from knowledge_master.cli import _check_convention
        assert _check_convention(tmp, "src/ directory") is True
        assert _check_convention(tmp, "separate test directory") is False


def test_convention_detection_tests_dir():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "tests").mkdir()
        from knowledge_master.cli import _check_convention
        assert _check_convention(tmp, "separate test directory") is True
