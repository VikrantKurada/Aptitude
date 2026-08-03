from aptitude.models import Document, Chunk
from aptitude.process.tokens import estimate_tokens

def _split_text(text, max_tokens, count):
    parts, buf = [], ""
    for para in text.split("\n\n") if "\n\n" in text else text.split(". "):
        candidate = (buf + "\n\n" + para).strip()
        if buf and count(candidate) > max_tokens:
            parts.append(buf.strip()); buf = para
        else:
            buf = candidate
    if buf.strip():
        parts.append(buf.strip())
    # hard-split any still-too-large part by characters
    out = []
    for p in parts:
        while count(p) > max_tokens:
            cut = max_tokens * 4
            out.append(p[:cut]); p = p[cut:]
        if p:
            out.append(p)
    return out

def chunk_document(doc: Document, max_tokens: int, count=estimate_tokens) -> list[Chunk]:
    chunks: list[Chunk] = []
    for sec in doc.sections:
        prov = f"{doc.title} › {sec.heading}"
        body = sec.text if not sec.code else f"{sec.text}\n\n```\n{sec.code}\n```"
        for piece in _split_text(body, max_tokens, count):
            chunks.append(Chunk(piece, count(piece), prov))
    return chunks
