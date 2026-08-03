from aptitude.models import Document, Source, Section
from aptitude.process.chunker import chunk_document

def _doc(*sections):
    return Document(Source("x"), "DocT", [Section(h, t) for h, t in sections])

def test_small_doc_one_chunk():
    chunks = chunk_document(_doc(("H1", "short text")), max_tokens=1000)
    assert len(chunks) == 1
    assert "DocT" in chunks[0].provenance and "H1" in chunks[0].provenance

def test_oversized_section_is_split():
    big = "para. " * 500  # ~3000 chars ≈ 750 tokens
    chunks = chunk_document(_doc(("Big", big)), max_tokens=100)
    assert len(chunks) > 1
    assert all(c.token_count <= 100 for c in chunks)
