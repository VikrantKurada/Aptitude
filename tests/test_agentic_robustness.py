import json
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.llm.base import LLMProvider, AssistantTurn, ToolCall
from aptitude.synthesize.agentic import AgenticSynthesizer
from aptitude.errors import ProviderError, SynthesisError

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

class _ScriptedChat(LLMProvider):
    """A minimal LLMProvider stub whose chat() returns pre-scripted AssistantTurns,
    so tests can produce multiple tool_calls in one turn (FakeProvider's ReAct
    default only ever yields <=1 call per turn)."""
    def __init__(self, turns=None, gen_responses=None):
        self.model = "s"
        self.context_window = 8000
        self._turns = list(turns or [])
        self._gen_responses = list(gen_responses or [])

    def generate(self, messages, **opts) -> str:
        if self._gen_responses:
            return self._gen_responses.pop(0)
        return "x"

    def chat(self, messages, tools):
        return self._turns.pop(0)

def test_parallel_tool_calls_do_not_break_loop():
    # First turn returns TWO tool calls; the loop must answer only one (keeping
    # the transcript's tool_use/tool_result pairing coherent) and still converge.
    turns = [
        AssistantTurn("", [ToolCall("c1", "read_source", {"index": 0}), ToolCall("c2", "read_source", {"index": 1})]),
        AssistantTurn("", [ToolCall("c3", "finish", {"name": "ok", "description": "Use when X.", "body": "b1"})]),
        AssistantTurn("", [ToolCall("c4", "finish", {"name": "ok", "description": "Use when X.", "body": "b2"})]),
    ]
    llm = _ScriptedChat(turns=turns)
    draft = AgenticSynthesizer(max_iterations=12).synthesize("p", _docs(), llm)
    assert draft.name == "ok" and draft.body == "b2"   # completed without a provider-shape error

def test_provider_error_falls_back_to_template():
    class _RaisingChat(_ScriptedChat):
        def chat(self, messages, tools):
            raise ProviderError("boom")
    llm = _RaisingChat(gen_responses=["name: fb-skill\ndescription: Use when X.", "body", "ref"])
    draft = AgenticSynthesizer(max_iterations=12).synthesize("p", _docs(), llm)
    assert draft.name == "fb-skill"
    assert any("template fallback" in p for p in draft.provenance)
