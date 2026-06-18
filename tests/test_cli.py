"""Unit tests for CLI."""

import subprocess
import sys
import os


def test_cli_help():
    result = subprocess.run([sys.executable, "-m", "knowledge_master", "--help"],
                           capture_output=True, text=True)
    assert result.returncode == 0
    assert "Knowledge Master" in result.stdout or "km" in result.stdout.lower()


def test_cli_status_no_db():
    """Invoke status when FalkorDB is unreachable — should handle error gracefully."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    script = (
        "import knowledge_master.store as st; "
        "st._graph_instance = None; "
        "st.get_graph = lambda **kw: (_ for _ in ()).throw(ConnectionError('test')); "
        "from knowledge_master.cli import app; "
        "from typer.testing import CliRunner; "
        "r = CliRunner().invoke(app, ['status']); "
        "print(r.output); "
        "assert r.exit_code == 0; "
        "assert 'FalkorDB' in r.output"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"
