# tests/test_summarizer.py
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.process.summarizer import distill

def _doc(text): return Document(Source("x"), "T", [Section("H", text)])

def test_passthrough_makes_no_llm_calls():
    """Under-budget passthrough must not call LLM."""
    doc = _doc("small body")
    class CountingLLM(FakeProvider):
        def __init__(self):
            super().__init__(responses=[])
            self.calls = 0

        def generate(self, messages, **opts):
            self.calls += 1
            return super().generate(messages, **opts)

    llm = CountingLLM()
    out = distill([doc], llm, budget=10000)
    assert "small body" in out
    assert llm.calls == 0

def test_over_budget_triggers_summarization():
    """Over-budget corpus triggers map-reduce with provenance headers."""
    doc = _doc("word " * 4000)  # ~5000 tokens
    llm = FakeProvider(responses=["SUMMARY"] * 50)
    out = distill([doc], llm, budget=200)
    assert "SUMMARY" in out
    assert "###" in out  # Provenance header must survive

def test_still_over_budget_triggers_final_reduce():
    """When concatenated summaries still exceed budget, final reduce is triggered."""
    doc = _doc("word " * 4000)  # Same oversized doc shape as existing test
    # 10 long chunk summaries so concatenation stays over budget,
    # then one final reduced response:
    llm = FakeProvider(responses=["S" * 400] * 10 + ["FINAL_REDUCED"])
    out = distill([doc], llm, budget=200)
    assert out == "FINAL_REDUCED"
