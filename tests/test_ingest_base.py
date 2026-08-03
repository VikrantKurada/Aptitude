import pytest
from aptitude.models import Source
from aptitude.ingest.base import detect_kind
from aptitude.errors import IngestionError

@pytest.mark.parametrize("raw,kind", [
    ("https://github.com/a/b", "github"),
    ("octocat/hello", "github"),
    ("https://example.com/page", "web"),
    ("book.epub", "epub"),
    ("/docs/file.pdf", "pdf"),
])
def test_detect_kind(raw, kind):
    assert detect_kind(raw) == kind

def test_detect_unknown_raises():
    with pytest.raises(IngestionError):
        detect_kind("mystery.xyz")
