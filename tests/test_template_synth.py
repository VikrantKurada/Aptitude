from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.synthesize.template_synth import TemplateSynthesizer

def _docs(): return [Document(Source("x"), "T", [Section("H", "content about privacy")])]

def test_synthesize_builds_draft():
    llm = FakeProvider(responses=[
        "name: privacy-policy-drafter\ndescription: Use when drafting GDPR privacy policies.",
        "## Instructions\nDo the thing.",
        "Reference material about GDPR.",
    ])
    draft = TemplateSynthesizer().synthesize("make a privacy skill", _docs(), llm)
    assert draft.name == "privacy-policy-drafter"
    assert "GDPR" in draft.description
    assert "Do the thing." in draft.body
    assert draft.references and "GDPR" in draft.references[0].content
    assert draft.provenance == ["x"]

def test_name_is_slugified_if_model_returns_spaces():
    llm = FakeProvider(responses=[
        "name: Privacy Policy Drafter\ndescription: d", "body", "ref"])
    draft = TemplateSynthesizer().synthesize("p", _docs(), llm)
    assert draft.name == "privacy-policy-drafter"

def test_unstructured_name_desc_falls_back_without_crashing():
    llm = FakeProvider(responses=["no structured output at all", "body text", "ref text"])
    draft = TemplateSynthesizer().synthesize("make a widget skill", _docs(), llm)
    assert draft.name == "skill"
    assert draft.description == "make a widget skill"

def test_name_key_present_but_empty_does_not_crash():
    llm = FakeProvider(responses=["intro text ending in name:", "body", "ref"])
    draft = TemplateSynthesizer().synthesize("p", _docs(), llm)
    assert draft.name
    assert "-" in draft.name or draft.name.isalnum()
