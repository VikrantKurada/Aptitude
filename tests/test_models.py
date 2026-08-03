# tests/test_models.py
from aptitude.models import Source, Document, Section, SkillDraft
from aptitude.errors import AptitudeError, IngestionError

def test_document_defaults_metadata():
    doc = Document(source=Source("a.pdf"), title="A", sections=[Section("H", "body")])
    assert doc.metadata == {}
    assert doc.sections[0].code is None

def test_skilldraft_default_collections_are_independent():
    a = SkillDraft(name="x", description="d", body="b")
    b = SkillDraft(name="y", description="d", body="b")
    a.references.append(object())
    assert b.references == []  # no shared mutable default

def test_source_default_kind_is_auto():
    assert Source("x").kind == "auto"

def test_error_hierarchy():
    assert issubclass(IngestionError, AptitudeError)
