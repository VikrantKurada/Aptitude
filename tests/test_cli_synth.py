# tests/test_cli_synth.py
import re
from typer.testing import CliRunner
from aptitude.cli import app
runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")  # Rich colorizes option dashes separately

def _plain(text: str) -> str:
    return _ANSI.sub("", text)

def test_create_with_agentic_synth(tmp_path):
    pdf = tmp_path / "d.pdf"
    from tests.fixtures.make_pdf import write_sample; write_sample(pdf)
    r = runner.invoke(app, ["create", "-p", "make a skill", "-i", str(pdf),
                            "--provider", "fake", "--synth", "agentic",
                            "--out", str(tmp_path / "out")])
    assert r.exit_code == 0
    assert list((tmp_path / "out").glob("*/SKILL.md"))

def test_create_help_lists_synth():
    # strip ANSI so the color-split option name (--synth) matches regardless of
    # whether Rich emits color (which differs by environment / TTY detection)
    out = _plain(runner.invoke(app, ["create", "--help"]).output)
    assert "--synth" in out and "--max-iterations" in out
