# tests/test_agent_tools.py
from aptitude.models import Document, Source, Section
from aptitude.synthesize.agent_tools import Toolbox, TOOL_SPECS

def _docs():
    return [Document(Source("a.pdf"), "DocA", [Section("Intro", "alpha "*10), Section("Body", "beta "*10)]),
            Document(Source("b.md"), "DocB", [Section("H", "gamma "*10)])]

def test_tool_specs_present():
    names = {t.name for t in TOOL_SPECS}
    assert {"list_sources", "read_source", "add_reference", "finish"} <= names

def test_list_sources_lists_titles_and_headings():
    out = Toolbox(_docs(), read_budget=10000).list_sources()
    assert "DocA" in out and "Intro" in out and "DocB" in out

def test_read_source_returns_section_text():
    tb = Toolbox(_docs(), read_budget=10000)
    assert "beta" in tb.read_source(0, section="Body")
    assert "alpha" in tb.read_source(0)          # whole doc when no section

def test_read_budget_exhaustion():
    tb = Toolbox(_docs(), read_budget=20)         # tiny budget
    tb.read_source(0)                             # consumes it
    assert "budget" in tb.read_source(1).lower()  # exhausted notice

def test_add_reference_accumulates():
    tb = Toolbox(_docs(), read_budget=10000)
    tb.add_reference("references/r.md", "distilled")
    assert tb.references[0].relpath == "references/r.md" and tb.references[0].content == "distilled"

def test_dispatch_unknown_tool_returns_error_not_raise():
    out = Toolbox(_docs(), read_budget=10000).dispatch("nope", {})
    assert "error" in out.lower() or "unknown" in out.lower()
