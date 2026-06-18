"""Unit tests for CLI."""

import subprocess
import sys


def test_cli_help():
    result = subprocess.run([sys.executable, "-m", "knowledge_master", "--help"],
                           capture_output=True, text=True)
    assert result.returncode == 0
    assert "Knowledge Master" in result.stdout or "km" in result.stdout.lower()


def test_cli_status_no_db():
    """Invoke status when FalkorDB is unreachable — should handle error gracefully."""
    # Run a script that patches get_graph to use an unreachable port, then calls status
    script = (
        "from unittest.mock import patch; "
        "from falkordb import FalkorDB; "
        "import knowledge_master.store as st; "
        "orig = st.get_graph; "
        "st.get_graph = lambda **kw: orig(port=19999); "
        "from knowledge_master.cli import app; "
        "from typer.testing import CliRunner; "
        "r = CliRunner().invoke(app, ['status']); "
        "print(r.output); "
        "assert r.exit_code == 0; "  # command doesn't crash
        "assert '✗' in r.output or 'error' in r.output.lower() or 'FalkorDB' in r.output"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15,
    )
    # The script itself should not crash with an unhandled exception
    assert result.returncode == 0, f"Script failed: {result.stderr}"
