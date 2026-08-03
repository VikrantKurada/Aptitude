from pathlib import Path
from aptitude.models import Source
from aptitude.ingest.pdf import PdfAdapter
from tests.fixtures.make_pdf import write_sample

def test_pdf_produces_document(tmp_path):
    p = tmp_path / "doc.pdf"; write_sample(p)
    doc = PdfAdapter().ingest(Source(str(p), "pdf"))
    assert doc.title == "doc"
    assert doc.metadata["pages"] == 1
    assert len(doc.sections) == 1
