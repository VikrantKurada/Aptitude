import re
from abc import ABC, abstractmethod
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
    if "github.com" in low or re.fullmatch(r"[\w.-]+/[\w.-]+", raw):
        return "github"
    if low.startswith("http://") or low.startswith("https://"):
        return "web"
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(".epub"):
        return "epub"
    raise IngestionError(f"cannot detect artifact type for '{raw}'")

def load(src: Source) -> Document:
    kind = src.kind if src.kind != "auto" else detect_kind(src.raw)
    return ingest_registry.get(kind)().ingest(src)
