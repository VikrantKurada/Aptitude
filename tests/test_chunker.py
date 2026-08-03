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


def test_small_sections_are_packed_into_one_chunk():
    # Three tiny sections should be combined into a single chunk, and the
    # chunk's provenance should name all three headings.
    doc = _doc(("H1", "one"), ("H2", "two"), ("H3", "three"))
    chunks = chunk_document(doc, max_tokens=1000)
    assert len(chunks) == 1
    prov = chunks[0].provenance
    assert "H1" in prov and "H2" in prov and "H3" in prov


def test_budget_is_honored_for_non_default_counter():
    # A run of text with no paragraph or sentence boundaries forces the
    # hard character-split fallback. With count=len (1 token/char), an
    # implementation that hardcodes a `max_tokens * 4` cut (assuming the
    # default ~4-chars-per-token estimator) blows the budget badly.
    big = "word " * 3000  # 15000 chars, no periods, no blank lines
    doc = _doc(("Big", big))
    chunks = chunk_document(doc, max_tokens=100, count=len)
    assert len(chunks) > 1
    assert all(len(c.text) <= 100 for c in chunks)


def test_sentence_split_preserves_periods_and_words():
    # Period-heavy single-paragraph text pushed through the sentence-tier
    # waterfall must not lose the sentence-ending periods, and must not
    # cut mid-word.
    sentences = "".join(f"Sentence {i}. " for i in range(1, 200))
    doc = _doc(("Prose", sentences))
    chunks = chunk_document(doc, max_tokens=50)
    assert all(c.token_count <= 50 for c in chunks)
    joined = "".join(c.text for c in chunks)
    for i in (1, 50, 100, 199):
        assert f"Sentence {i}." in joined


def test_empty_section_does_not_crash():
    doc = _doc(("Empty", ""), ("Real", "some content"))
    chunks = chunk_document(doc, max_tokens=1000)
    assert any("some content" in c.text for c in chunks)


def test_section_with_code_is_represented():
    doc = Document(Source("x"), "DocT", [Section("Code", "See below", code="print('hi')")])
    chunks = chunk_document(doc, max_tokens=1000)
    assert any("print('hi')" in c.text for c in chunks)
