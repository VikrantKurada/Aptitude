from pathlib import Path
from typer.testing import CliRunner
from aptitude.cli import app

runner = CliRunner()

def test_all_commands_have_help():
    for cmd in ["create", "providers", "formats", "validate", "init"]:
        assert runner.invoke(app, [cmd, "--help"]).exit_code == 0

def test_readme_mentions_all_providers():
    text = Path("README.md").read_text()
    for p in ["claude", "gemini", "nvidia", "ollama", "openai"]:
        assert p in text
