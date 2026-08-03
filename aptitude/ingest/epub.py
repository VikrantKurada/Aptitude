from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

@ingest_registry.register("epub")
class EpubAdapter(IngestionAdapter):
    name = "epub"
    def can_handle(self, src): return src.raw.lower().endswith(".epub")
    def ingest(self, src) -> Document:
        try:
            book = epub.read_epub(src.raw)
        except Exception as e:
            raise IngestionError(f"cannot read EPUB {src.raw}: {e}") from e
        title = (book.get_metadata("DC", "title") or [("Untitled",)])[0][0]
        sections = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            text = BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True)
            if text:
                sections.append(Section(item.get_name(), text))
        return Document(src, title, sections, {"items": len(sections)})
