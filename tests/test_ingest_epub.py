from aptitude.models import Source
from aptitude.ingest.epub import EpubAdapter
from tests.fixtures.make_epub import write_sample

def test_epub_extracts_text(tmp_path):
    p = tmp_path / "b.epub"; write_sample(p)
    doc = EpubAdapter().ingest(Source(str(p), "epub"))
    assert doc.title == "Sample Book"
    assert any("Hello epub world" in s.text for s in doc.sections)
    # the EPUB3 nav/TOC document (nav.xhtml) must not be emitted as content
    assert len(doc.sections) == 1
    assert doc.metadata["items"] == 1
    assert not any(s.heading == "nav.xhtml" for s in doc.sections)
