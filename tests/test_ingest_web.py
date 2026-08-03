# tests/test_ingest_web.py
from aptitude.models import Source
from aptitude.ingest.web import WebAdapter

HTML = """<html><head><title>My Page</title></head>
<body><nav>menu junk</nav><main><h1>Heading</h1><p>Real content here.</p></main>
<footer>footer junk</footer></body></html>"""

def test_web_extracts_main_content():
    doc = WebAdapter(fetch=lambda url: HTML).ingest(Source("https://x.test", "web"))
    assert doc.title == "My Page"
    body = " ".join(s.text for s in doc.sections)
    assert "Real content here." in body
    assert "menu junk" not in body and "footer junk" not in body
