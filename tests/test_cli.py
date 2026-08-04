# tests/test_cli.py
from typer.testing import CliRunner
from aptitude.cli import app

runner = CliRunner()

def test_formats_lists_claude_skill():
    r = runner.invoke(app, ["formats"])
    assert r.exit_code == 0 and "claude-skill" in r.output

def test_create_with_fake_provider(tmp_path, monkeypatch):
    pdf = tmp_path / "d.pdf"
    from tests.fixtures.make_pdf import write_sample; write_sample(pdf)
    r = runner.invoke(app, ["create", "-p", "make a skill", "-i", str(pdf),
                            "--provider", "fake", "--out", str(tmp_path / "out")])
    assert r.exit_code == 0
    assert list((tmp_path / "out").glob("*/SKILL.md"))

def test_create_format_override_and_verbose(tmp_path):
    pdf = tmp_path / "d.pdf"
    from tests.fixtures.make_pdf import write_sample; write_sample(pdf)
    out = tmp_path / "out"
    r = runner.invoke(app, ["create", "-p", "make a skill", "-i", str(pdf),
                            "--provider", "fake", "--format", "generic-prompt",
                            "--out", str(out), "-v"])
    assert r.exit_code == 0
    assert list(out.glob("*/*.json"))          # generic-prompt output, not SKILL.md
    assert "provider: fake" in r.output        # verbose header
    assert "wrote" in r.output                 # verbose per-file listing

def test_validate_command(tmp_path):
    d = tmp_path / "s"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: s\ndescription: Use when X.\n---\nbody")
    r = runner.invoke(app, ["validate", str(d)])
    assert r.exit_code == 0
