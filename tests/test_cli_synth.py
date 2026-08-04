# tests/test_cli_synth.py
from typer.testing import CliRunner
from aptitude.cli import app
runner = CliRunner()

def test_create_with_agentic_synth(tmp_path):
    pdf = tmp_path / "d.pdf"
    from tests.fixtures.make_pdf import write_sample; write_sample(pdf)
    r = runner.invoke(app, ["create", "-p", "make a skill", "-i", str(pdf),
                            "--provider", "fake", "--synth", "agentic",
                            "--out", str(tmp_path / "out")])
    assert r.exit_code == 0
    assert list((tmp_path / "out").glob("*/SKILL.md"))

def test_create_help_lists_synth():
    assert "--synth" in runner.invoke(app, ["create", "--help"]).output
