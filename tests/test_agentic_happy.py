# tests/test_agentic_happy.py
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.synthesize.agentic import AgenticSynthesizer

def _docs():
    return [Document(Source("a.pdf"), "DocA", [Section("Body", "important facts about widgets")])]

def _action(tool, **args):
    import json
    return f'```action\n{json.dumps({"tool": tool, "arguments": args})}\n```'

def test_agentic_full_session_builds_draft():
    # explore -> read -> add_reference -> finish -> (forced critique) -> finish
    llm = FakeProvider(responses=[
        _action("list_sources"),
        _action("read_source", index=0),
        _action("add_reference", relpath="references/facts.md", content="widget facts"),
        _action("finish", name="Widget Skill", description="Use when building widgets", body="Draft body"),
        _action("finish", name="Widget Skill", description="Use when building widgets", body="Improved body"),
    ])
    draft = AgenticSynthesizer(max_iterations=12).synthesize("make a widget skill", _docs(), llm)
    assert draft.name == "widget-skill"                         # slugified
    assert draft.description == "Use when building widgets"
    assert draft.body == "Improved body"                        # the post-critique finish won
    assert any(f.relpath == "references/facts.md" for f in draft.references)
    assert draft.provenance == ["a.pdf"]

def test_agentic_registered():
    from aptitude.synthesize.base import synth_registry
    assert synth_registry.get("agentic") is AgenticSynthesizer
