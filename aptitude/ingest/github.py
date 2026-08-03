import re, subprocess, tempfile
from pathlib import Path
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

_SIG = re.compile(r"^\s*(def |class |function |export (default )?|async def )", re.M)
_CODE_EXT = {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java"}

def _default_clone(raw: str) -> Path:
    url = raw if raw.startswith("http") else f"https://github.com/{raw}.git"
    dest = Path(tempfile.mkdtemp(prefix="aptitude-repo-"))
    r = subprocess.run(["git", "clone", "--depth", "1", url, str(dest)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise IngestionError(f"git clone failed for {raw}: {r.stderr.strip()}")
    return dest

@ingest_registry.register("github")
class GithubAdapter(IngestionAdapter):
    name = "github"
    def __init__(self, clone=None):
        self._clone = clone or _default_clone
    def can_handle(self, src):
        return "github.com" in src.raw or bool(re.fullmatch(r"[\w.-]+/[\w.-]+", src.raw))
    def ingest(self, src) -> Document:
        root = Path(self._clone(src.raw))
        sections, n = [], 0
        for readme in sorted(root.glob("README*")):
            sections.append(Section(readme.name, readme.read_text(errors="ignore")))
        sigs = []
        for f in sorted(root.rglob("*")):
            if f.suffix in _CODE_EXT and ".git" not in f.parts:
                n += 1
                lines = [ln.strip() for ln in f.read_text(errors="ignore").splitlines()
                         if _SIG.match(ln)]
                if lines:
                    sigs.append(f"{f.relative_to(root)}:\n  " + "\n  ".join(lines))
        if sigs:
            sections.append(Section("Code structure", "\n\n".join(sigs)))
        if not sections:
            raise IngestionError(f"no readable content in repo {src.raw}")
        return Document(src, root.name, sections, {"files": n})
