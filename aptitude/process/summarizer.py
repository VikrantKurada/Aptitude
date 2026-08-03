from aptitude.process.tokens import estimate_tokens
from aptitude.process.chunker import chunk_document

def _corpus(docs):
    blocks = []
    for d in docs:
        for s in d.sections:
            blocks.append(f"## {d.title} › {s.heading}\n{s.text}")
    return "\n\n".join(blocks)

def _summarize_chunk(llm, chunk):
    msg = [{"role": "user",
            "content": f"Summarize the following source excerpt, preserving key "
                       f"facts, terminology, and steps. Excerpt from {chunk.provenance}:"
                       f"\n\n{chunk.text}"}]
    return f"### {chunk.provenance}\n{llm.generate(msg)}"

def distill(docs, llm, budget: int) -> str:
    corpus = _corpus(docs)
    if estimate_tokens(corpus) <= budget:
        return corpus
    chunks = [c for d in docs for c in chunk_document(d, max_tokens=max(500, budget // 4))]
    summaries = [_summarize_chunk(llm, c) for c in chunks]
    reduced = "\n\n".join(summaries)
    if estimate_tokens(reduced) > budget:
        msg = [{"role": "user",
                "content": f"Condense these notes to under {budget} tokens, keeping "
                           f"provenance headers:\n\n{reduced}"}]
        reduced = llm.generate(msg)
    return reduced
