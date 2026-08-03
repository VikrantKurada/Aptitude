from pathlib import Path
from aptitude.models import Source
from aptitude.ingest.github import GithubAdapter

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
