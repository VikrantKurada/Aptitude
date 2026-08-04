import re, subprocess, tempfile
from pathlib import Path
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

_SIG = re.compile(r"^\s*(def |class |function |export (default )?|async def |pub fn |fn |func )", re.M)
_CODE_EXT = {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java"}

def _repo_name(raw: str) -> str:
    last = raw.rstrip("/").rsplit("/", 1)[-1]
    if last.endswith(".git"):
        last = last[: -len(".git")]
    return last

def _default_clone(raw: str) -> Path:
    url = raw if raw.startswith("http") else f"https://github.com/{raw}.git"
    parent = Path(tempfile.mkdtemp(prefix="aptitude-repo-"))
    target = parent / _repo_name(raw)
    try:
        r = subprocess.run(["git", "clone", "--depth", "1", url, str(target)],
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as e:
        raise IngestionError(f"git clone timed out after 300s for {raw}") from e
    if r.returncode != 0:
        raise IngestionError(f"git clone failed for {raw}: {r.stderr.strip()}")
    return target

@ingest_registry.register("github")
class GithubAdapter(IngestionAdapter):
    name = "github"
    def __init__(self, clone=None):
        self._clone = clone or _default_clone
    def ingest(self, src) -> Document:
        root = Path(self._clone(src.raw))
        sections, n = [], 0
        for readme in sorted(root.glob("README*")):
            sections.append(Section(readme.name, readme.read_text(encoding="utf-8", errors="ignore")))
        docs_dir = root / "docs"
        if docs_dir.is_dir():
            for f in sorted(docs_dir.rglob("*.md")):
                if f.is_file():
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    if content.strip():
                        sections.append(Section(str(f.relative_to(root)), content[:4000]))
        sigs = []
        for f in sorted(root.rglob("*")):
            if f.suffix in _CODE_EXT and ".git" not in f.parts and f.is_file():
                n += 1
                lines = [ln.strip() for ln in f.read_text(encoding="utf-8", errors="ignore").splitlines()
                         if _SIG.match(ln)]
                if lines:
                    sigs.append(f"{f.relative_to(root)}:\n  " + "\n  ".join(lines))
        if sigs:
            sections.append(Section("Code structure", "\n\n".join(sigs)))
        if not sections:
            raise IngestionError(f"no readable content in repo {src.raw}")
        return Document(src, root.name, sections, {"files": n})
