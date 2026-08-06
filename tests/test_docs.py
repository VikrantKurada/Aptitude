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
LINK = re.compile(r"\[[^\]]*?\]\(([^)]+)\)")


def _doc_paths() -> list[Path]:
    """README plus every docs page, excluding the specs/plans archive."""
    paths = [ROOT / "README.md"]
    paths += sorted(p for p in (ROOT / "docs").rglob("*.md")
                    if "superpowers" not in p.relative_to(ROOT).parts)
    return [p for p in paths if p.exists()]


def _corpus() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _doc_paths())


def _strip_fenced_blocks(text: str) -> str:
    """Remove fenced code blocks (``` ... ```) from text."""
    return re.sub(r"```[\s\S]*?```", "", text)


def _links_in(text: str) -> list[str]:
    """Extract all link targets from text, handling nested brackets and stripping fenced blocks.

    Handles:
    - Nested brackets (image links with outer link): [![](img.png)](target.md)
    - Fenced code blocks: links inside ``` ... ``` are ignored
    """
    text = _strip_fenced_blocks(text)
    links = set()

    # Find all ](...) patterns. For nested brackets like [![...](img)](...),
    # this regex finds both the inner and outer targets.
    for match in re.finditer(r"\]\(([^)]+)\)", text):
        pos = match.start()
        # Verify there's an opening [ bracket somewhere before this ]
        # This ensures we're matching actual markdown links, not random ](...)
        if "[" in text[:pos]:
            target = match.group(1).split()[0]  # drop optional "title"
            if target and not target.startswith(("http://", "https://", "mailto:", "#")):
                links.add(target)

    return sorted(links)


def _resolve_link(target: str, file_path: Path) -> Path:
    """Resolve a link target relative to the file containing it.

    Handles:
    - Root-relative paths (starting with /) → resolve against ROOT
    - Relative paths → resolve against file's parent directory
    - Anchors → strip before resolving
    """
    # Strip anchor
    target_path = target.split("#")[0]

    if not target_path:
        return Path()

    # Root-relative paths resolve against ROOT
    if target_path.startswith("/"):
        return ROOT / target_path.lstrip("/")

    # Relative paths resolve against file's parent
    return file_path.parent / target_path


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
        content = path.read_text(encoding="utf-8")
        for target in _links_in(content):
            resolved = _resolve_link(target, path)
            if resolved.name and not resolved.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, "broken relative links: " + ", ".join(broken)


# Regression tests for link checker edge cases

def test_nested_bracket_links_are_caught():
    r"""Finding 1: Nested brackets like [![img](img.png)](real-target.md) must check real-target.md.

    Old regex [^\]]* stops at the first ] and misses the outer link.
    This test ensures the outer link is extracted and verified.
    """
    # Image link that points to a nonexistent file
    text = "[![diagram](diagram.png)](does-not-exist.md)"
    links = _links_in(text)
    # Should extract the outer link destination, not just the image
    assert "does-not-exist.md" in links


def test_links_in_fenced_code_blocks_are_ignored():
    r"""Finding 2: Links inside fenced code blocks are examples, not real links.

    Upcoming docs show generated SKILL.md content in fences.
    A link inside a fence should not be resolved as a real file.
    """
    text = """
Some text.

```markdown
[example link](does-not-exist.md)
```

More text.
"""
    links = _links_in(text)
    # The link inside the fence should be stripped out
    assert "does-not-exist.md" not in links


def test_root_relative_links_resolve_correctly():
    """Finding 3: Root-relative paths starting with / must resolve against ROOT, not file parent.

    A link like /docs/foo.md should check ROOT/docs/foo.md, not file.parent/docs/foo.md.
    """
    # Create a fake test path
    test_file = ROOT / "README.md"

    # Test that root-relative path resolves to ROOT
    resolved = _resolve_link("/README.md", test_file)
    assert resolved == ROOT / "README.md"

    # Test that relative path still resolves to file parent
    resolved = _resolve_link("README.md", test_file)
    assert resolved == test_file.parent / "README.md"
