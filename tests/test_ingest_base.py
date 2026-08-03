import pytest
from aptitude.ingest.base import detect_kind
from aptitude.errors import IngestionError

@pytest.mark.parametrize("raw,kind", [
    # Original cases
    ("https://github.com/a/b", "github"),
    ("octocat/hello", "github"),
    ("https://example.com/page", "web"),
    ("book.epub", "epub"),
    ("/docs/file.pdf", "pdf"),
    # Bug fixes: extension wins even with slashes in path
    ("docs/file.pdf", "pdf"),
    ("notes/readme.epub", "epub"),
    # Bug fixes: github.com host check
    ("https://notgithub.com.evil.com/page", "web"),
])
def test_detect_kind(raw, kind):
    assert detect_kind(raw) == kind

def test_detect_unknown_raises():
    with pytest.raises(IngestionError):
        detect_kind("mystery.xyz")

def test_detect_schemeless_domain_raises():
    """Schemeless domain like example.com/page is not a valid repo shorthand."""
    with pytest.raises(IngestionError):
        detect_kind("example.com/page")
