import json
from aptitude.models import SkillDraft, SkillFile
from aptitude.export.generic_prompt import GenericPromptExporter
from aptitude.export.local_llm import LocalLlmExporter

def _draft():
    return SkillDraft(name="s", description="Use when X.", body="Body here.",
                      references=[SkillFile("references/r.md", "REF")])

def test_generic_prompt_md_and_json(tmp_path):
    GenericPromptExporter().export(_draft(), tmp_path)
    md = (tmp_path / "s" / "s.md").read_text()
    assert "Body here." in md and "REF" in md
    data = json.loads((tmp_path / "s" / "s.json").read_text())
    assert data["name"] == "s" and "Body here." in data["system_prompt"]

def test_local_llm_modelfile_and_system(tmp_path):
    LocalLlmExporter().export(_draft(), tmp_path)
    mf = (tmp_path / "s" / "Modelfile").read_text()
    assert mf.startswith("FROM ") and "SYSTEM" in mf
    assert "Body here." in (tmp_path / "s" / "system.txt").read_text()
