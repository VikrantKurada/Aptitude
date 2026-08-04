import json
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.synthesize.agentic import AgenticSynthesizer
from aptitude.errors import SynthesisError

def _docs():
    return [Document(Source("a.pdf"), "T", [Section("H", "content about things")])]

def _action(tool, **a):
    return f'```action\n{json.dumps({"tool": tool, "arguments": a})}\n```'

def test_never_finishing_falls_back_to_template():
    # agent keeps listing sources, never finishes; then template's 3 calls answer
    loops = [_action("list_sources")] * 12
    template = ["name: fallback-skill\ndescription: Use when X.", "body", "ref"]
    llm = FakeProvider(responses=loops + template)
    draft = AgenticSynthesizer(max_iterations=12).synthesize("p", _docs(), llm)
    assert draft.name == "fallback-skill"
    assert any("template fallback" in p for p in draft.provenance)

def test_no_fallback_raises():
    llm = FakeProvider(responses=[_action("list_sources")] * 3)
    with __import__("pytest").raises(SynthesisError):
        AgenticSynthesizer(max_iterations=3, fallback=False).synthesize("p", _docs(), llm)

def test_malformed_tool_call_is_recoverable():
    # unknown tool -> error observation -> agent recovers and finishes (x2 for critique)
    llm = FakeProvider(responses=[
        _action("bogus_tool"),
        _action("finish", name="ok skill", description="Use when Y.", body="b1"),
        _action("finish", name="ok skill", description="Use when Y.", body="b2"),
    ])
    draft = AgenticSynthesizer(max_iterations=12).synthesize("p", _docs(), llm)
    assert draft.name == "ok-skill" and draft.body == "b2"
