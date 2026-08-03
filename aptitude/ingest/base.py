import re
from abc import ABC, abstractmethod
from urllib.parse import urlsplit
from aptitude.models import Source, Document
from aptitude.registry import Registry
from aptitude.errors import IngestionError

ingest_registry = Registry("adapter")

class IngestionAdapter(ABC):
    name: str = "base"
    @abstractmethod
    def can_handle(self, src: Source) -> bool: ...
    @abstractmethod
    def ingest(self, src: Source) -> Document: ...

def detect_kind(raw: str) -> str:
    low = raw.lower()
    # extension is most specific — wins even when the path contains a slash
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(".epub"):
        return "epub"
    # URLs: separate github.com host from generic web via parsed netloc
    if low.startswith("http://") or low.startswith("https://"):
        host = urlsplit(low).netloc
        if host == "github.com" or host.endswith(".github.com"):
            return "github"
        return "web"
    # bare owner/repo shorthand: owner segment has NO dots (github usernames can't),
    # which excludes schemeless domains like "example.com/page"
    if re.fullmatch(r"[\w-]+/[\w.-]+", raw):
        return "github"
    raise IngestionError(f"cannot detect artifact type for '{raw}'")

def load(src: Source) -> Document:
    kind = src.kind if src.kind != "auto" else detect_kind(src.raw)
    return ingest_registry.get(kind)().ingest(src)
