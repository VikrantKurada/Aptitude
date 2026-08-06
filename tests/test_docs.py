import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aptitude.cli import app  # importing the CLI registers every provider/format
from aptitude.config import DEFAULT_MODELS
from aptitude.export.base import export_registry

runner = CliRunner()

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = ["create", "providers", "formats", "validate", "init"]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _doc_paths() -> list[Path]:
    """README plus every docs page, excluding the specs/plans archive."""
    paths = [ROOT / "README.md"]
    paths += sorted(p for p in (ROOT / "docs").rglob("*.md")
                    if "superpowers" not in p.relative_to(ROOT).parts)
    return [p for p in paths if p.exists()]


def _corpus() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _doc_paths())


def test_all_commands_have_help():
    for cmd in COMMANDS:
        assert runner.invoke(app, [cmd, "--help"]).exit_code == 0


@pytest.mark.parametrize("provider", sorted(DEFAULT_MODELS))
def test_docs_mention_every_provider(provider):
    assert provider in _corpus()


@pytest.mark.parametrize("fmt", sorted(export_registry.names()))
def test_docs_mention_every_format(fmt):
    assert fmt in _corpus()


@pytest.mark.parametrize("cmd", COMMANDS)
def test_docs_mention_every_command(cmd):
    assert cmd in _corpus()


def test_relative_links_resolve():
    broken = []
    for path in _doc_paths():
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            target = target.split()[0]                      # drop optional "title"
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel = target.split("#")[0]                       # drop anchor
            if rel and not (path.parent / rel).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, "broken relative links: " + ", ".join(broken)
