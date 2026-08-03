from aptitude.models import Source
from aptitude.ingest.epub import EpubAdapter
from tests.fixtures.make_epub import write_sample

def test_epub_extracts_text(tmp_path):
    p = tmp_path / "b.epub"; write_sample(p)
    doc = EpubAdapter().ingest(Source(str(p), "epub"))
    assert doc.title == "Sample Book"
    assert any("Hello epub world" in s.text for s in doc.sections)
