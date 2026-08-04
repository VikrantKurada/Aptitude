from pathlib import Path
from pypdf import PdfReader
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

@ingest_registry.register("pdf")
class PdfAdapter(IngestionAdapter):
    name = "pdf"
    def ingest(self, src) -> Document:
        path = Path(src.raw)
        if not path.exists():
            raise IngestionError(f"PDF not found: {path}")
        reader = PdfReader(str(path))
        sections = [Section(f"Page {i+1}", (pg.extract_text() or "").strip())
                    for i, pg in enumerate(reader.pages)]
        return Document(src, path.stem, sections, {"pages": len(reader.pages)})
