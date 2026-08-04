# tests/test_pipeline.py
from pathlib import Path
from aptitude.models import Source
from aptitude.llm.fake import FakeProvider
from aptitude.pipeline import RunConfig, run
from aptitude.ingest.base import ingest_registry, IngestionAdapter
from aptitude.models import Document, Section

class _StubAdapter(IngestionAdapter):
    name = "stub"
    def ingest(self, src):
        if "bad" in src.raw:
            raise Exception("boom")
        return Document(src, "T", [Section("H", "content")])

def _cfg(tmp_path, raws, dry=False):
    return RunConfig(prompt="make skill", sources=[Source(r, "stub") for r in raws],
                     provider="fake", model=None, formats=["claude-skill"],
                     out=tmp_path, budget=6000, dry_run=dry)

def test_end_to_end_writes_skill(tmp_path, monkeypatch):
    monkeypatch.setitem(ingest_registry._items, "stub", _StubAdapter)
    llm = FakeProvider(responses=["name: my-skill\ndescription: Use when X.",
                                  "## Body", "ref"])
    res = run(_cfg(tmp_path, ["a.stub"]), llm)
    assert res.exit_code == 0
    assert (tmp_path / "my-skill" / "SKILL.md").exists()

def test_partial_failure_skips_and_continues(tmp_path, monkeypatch):
    monkeypatch.setitem(ingest_registry._items, "stub", _StubAdapter)
    llm = FakeProvider(responses=["name: my-skill\ndescription: Use when X.", "b", "r"])
    res = run(_cfg(tmp_path, ["bad.stub", "ok.stub"]), llm)
    assert res.exit_code == 1 and res.skipped and res.draft is not None

def test_all_fail_is_fatal(tmp_path, monkeypatch):
    monkeypatch.setitem(ingest_registry._items, "stub", _StubAdapter)
    res = run(_cfg(tmp_path, ["bad1.stub", "bad2.stub"]), FakeProvider())
    assert res.exit_code == 2 and res.draft is None

def test_dry_run_stops_before_synthesis(tmp_path, monkeypatch):
    monkeypatch.setitem(ingest_registry._items, "stub", _StubAdapter)
    res = run(_cfg(tmp_path, ["a.stub"], dry=True), FakeProvider())
    assert res.draft is None
    assert res.corpus is not None
    assert res.written == []
    assert res.exit_code == 0
