# aptitude/ingest/web.py
import httpx
from bs4 import BeautifulSoup
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

def _default_fetch(url: str) -> str:
    r = httpx.get(url, follow_redirects=True, timeout=30,
                  headers={"User-Agent": "Aptitude/0.1"})
    r.raise_for_status()
    return r.text

@ingest_registry.register("web")
class WebAdapter(IngestionAdapter):
    name = "web"
    def __init__(self, fetch=None):
        self._fetch = fetch or _default_fetch
    def ingest(self, src) -> Document:
        try:
            html = self._fetch(src.raw)
        except Exception as e:
            raise IngestionError(f"cannot fetch {src.raw}: {e}") from e
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        title = (soup.title.string if soup.title else None) or \
                (soup.h1.get_text(strip=True) if soup.h1 else src.raw)
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = main.get_text("\n", strip=True)
        return Document(src, title.strip(), [Section("Content", text)], {"url": src.raw})
