import subprocess
from pathlib import Path
from aptitude.models import Source
from aptitude.ingest.github import GithubAdapter, _default_clone

def _make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)          # create the dir BEFORE writing files
    (root / "README.md").write_text("# Cool Repo\nDoes cool things.")
    (root / "app.py").write_text("import os\n\ndef run(x):\n    return x\n\nclass Engine:\n    pass\n")
    return root

def test_github_reads_readme_and_signatures(tmp_path):
    repo = _make_repo(tmp_path / "cool-repo")
    doc = GithubAdapter(clone=lambda raw: repo).ingest(Source("owner/cool-repo", "github"))
    text = "\n".join(s.text for s in doc.sections)
    assert "Does cool things." in text
    assert "def run(x)" in text and "class Engine" in text

def test_default_clone_uses_repo_name_as_dir(monkeypatch):
    captured = {}
    def fake_run(args, **kwargs):
        captured["args"] = args
        dest = Path(args[-1])
        dest.mkdir(parents=True, exist_ok=True)
        class FakeResult:
            returncode = 0
            stderr = ""
        return FakeResult()
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = _default_clone("owner/coolrepo")
    assert result.name == "coolrepo"
    assert captured["args"][-1].endswith("coolrepo")

def test_github_reads_docs_markdown(tmp_path):
    repo = _make_repo(tmp_path / "docs-repo")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("Guide content here.")
    (repo / "docs" / "long.md").write_text("x" * 5000)
    doc = GithubAdapter(clone=lambda raw: repo).ingest(Source("owner/docs-repo", "github"))
    combined = "\n".join(s.text for s in doc.sections)
    assert "Guide content here." in combined
    long_section = next(s for s in doc.sections if "long.md" in s.heading)
    assert len(long_section.text) == 4000

def test_github_signatures_go_and_rust(tmp_path):
    repo = _make_repo(tmp_path / "polyglot-repo")
    (repo / "main.go").write_text("package main\n\nfunc Foo() {}\n")
    (repo / "lib.rs").write_text("pub fn bar() {}\n")
    doc = GithubAdapter(clone=lambda raw: repo).ingest(Source("owner/polyglot-repo", "github"))
    text = "\n".join(s.text for s in doc.sections)
    assert "func Foo" in text
    assert "pub fn bar" in text or "fn bar" in text
