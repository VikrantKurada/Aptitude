# tests/test_summarizer.py
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.process.summarizer import distill

def _doc(text): return Document(Source("x"), "T", [Section("H", text)])

def test_under_budget_passthrough_no_llm_calls():
    doc = _doc("small body")
    out = distill([doc], FakeProvider(responses=[]), budget=10000)
    assert "small body" in out

def test_over_budget_triggers_summarization():
    doc = _doc("word " * 4000)  # ~5000 tokens
    llm = FakeProvider(responses=["SUMMARY"] * 50)
    out = distill([doc], llm, budget=200)
    assert "SUMMARY" in out
