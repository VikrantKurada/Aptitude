"""Split a Document into token-bounded Chunks.

Each Section's body is broken into "units" -- pieces of text individually
guaranteed to satisfy ``count(piece) <= max_tokens`` -- via a paragraph ->
sentence -> hard character-split waterfall. Units are then greedily packed,
in order, into as few Chunks as possible while staying under max_tokens, so
several small sections can share a single chunk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from aptitude.models import Chunk, Document, Section
from aptitude.process.tokens import estimate_tokens

_PARAGRAPH_SEP = "\n\n"
# Split *after* each ". " so the delimiter (period + space) stays attached
# to the sentence that precedes it -- splitting never drops characters.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=\. )")

Counter = Callable[[str], int]


@dataclass
class _Unit:
    """A piece of a section's text, guaranteed to fit within max_tokens."""

    heading: str
    text: str


def _hard_split(text: str, max_tokens: int, count: Counter) -> list[str]:
    """Last-resort split: cut ``text`` into pieces with count(piece) <=
    max_tokens by binary-searching the largest fitting prefix each time.

    Always makes progress (emits at least one character per piece), even in
    the pathological case where a single character exceeds the budget.
    """
    pieces: list[str] = []
    while text:
        if count(text) <= max_tokens:
            pieces.append(text)
            break
        lo, hi, best = 1, len(text), 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if count(text[:mid]) <= max_tokens:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        pieces.append(text[:best])
        text = text[best:]
    return pieces


def _split_by_sentence(text: str, max_tokens: int, count: Counter) -> list[str]:
    """Split on sentence boundaries; hard-split any sentence still over
    budget. Sentence delimiters are preserved (see _SENTENCE_SPLIT_RE)."""
    if count(text) <= max_tokens:
        return [text]
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s]
    if len(sentences) <= 1:
        return _hard_split(text, max_tokens, count)
    pieces: list[str] = []
    for sentence in sentences:
        if count(sentence) <= max_tokens:
            pieces.append(sentence)
        else:
            pieces.extend(_hard_split(sentence, max_tokens, count))
    return pieces


def _split_by_paragraph(text: str, max_tokens: int, count: Counter) -> list[str]:
    """Split on paragraph boundaries (blank lines); any paragraph still
    over budget falls through to sentence-then-hard-char splitting."""
    if count(text) <= max_tokens:
        return [text]
    paragraphs = [p for p in text.split(_PARAGRAPH_SEP) if p]
    if len(paragraphs) <= 1:
        return _split_by_sentence(text, max_tokens, count)
    pieces: list[str] = []
    for para in paragraphs:
        if count(para) <= max_tokens:
            pieces.append(para)
        else:
            pieces.extend(_split_by_sentence(para, max_tokens, count))
    return pieces


def _section_body(sec: Section) -> str:
    if sec.code:
        return f"{sec.text}\n\n```\n{sec.code}\n```"
    return sec.text


def _build_units(doc: Document, max_tokens: int, count: Counter) -> list[_Unit]:
    units: list[_Unit] = []
    for sec in doc.sections:
        body = _section_body(sec)
        if not body:
            continue
        for piece in _split_by_paragraph(body, max_tokens, count):
            if piece:
                units.append(_Unit(sec.heading, piece))
    return units


def _pack_units(
    units: list[_Unit], max_tokens: int, count: Counter, doc_title: str
) -> list[Chunk]:
    """Greedily combine consecutive units into a chunk while the running
    count stays <= max_tokens; start a new chunk only when the next unit
    would not fit."""
    chunks: list[Chunk] = []
    cur_texts: list[str] = []
    cur_headings: list[str] = []

    def flush() -> None:
        if not cur_texts:
            return
        text = _PARAGRAPH_SEP.join(cur_texts)
        provenance = f"{doc_title} › " + ", ".join(cur_headings)
        chunks.append(Chunk(text, count(text), provenance))

    for unit in units:
        candidate_texts = cur_texts + [unit.text]
        candidate = _PARAGRAPH_SEP.join(candidate_texts)
        if cur_texts and count(candidate) > max_tokens:
            flush()
            cur_texts = [unit.text]
            cur_headings = [unit.heading]
        else:
            cur_texts = candidate_texts
            if unit.heading not in cur_headings:
                cur_headings.append(unit.heading)
    flush()
    return chunks


def chunk_document(
    doc: Document, max_tokens: int, count: Counter = estimate_tokens
) -> list[Chunk]:
    """Pack doc's sections into Chunks, each with count(chunk.text) <=
    max_tokens.

    Oversized sections are split on paragraph, then sentence, then (as a
    last resort) raw character boundaries -- always honoring whatever
    ``count`` callable is supplied, not just the default estimator.
    Consecutive small units (including across sections) are packed
    together into a single chunk.
    """
    units = _build_units(doc, max_tokens, count)
    return _pack_units(units, max_tokens, count, doc.title)
