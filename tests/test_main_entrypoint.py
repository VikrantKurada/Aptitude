"""Verify `python -m aptitude` launches the CLI (what start.ps1/start.sh invoke)."""
import subprocess
import sys

from aptitude.cli import app


def test_main_module_exposes_cli_app():
    import aptitude.__main__ as m

    assert m.app is app


def test_python_m_aptitude_runs():
    result = subprocess.run(
        [sys.executable, "-m", "aptitude", "formats"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "claude-skill" in result.stdout
