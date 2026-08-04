from aptitude.models import SkillDraft, SkillFile
from aptitude.export.claude_skill import ClaudeSkillExporter
from tests.export_contract import assert_exporter_contract

def _draft():
    return SkillDraft(name="my-skill", description="Use when testing.",
                      body="## Steps\nDo it.",
                      references=[SkillFile("references/r.md", "ref body")])

def test_claude_skill_layout(tmp_path):
    paths = assert_exporter_contract(ClaudeSkillExporter(), _draft(), tmp_path)
    skill_md = (tmp_path / "my-skill" / "SKILL.md").read_text()
    assert skill_md.startswith("---\n")
    assert "name: my-skill" in skill_md and "description: Use when testing." in skill_md
    assert "## Steps" in skill_md
    assert (tmp_path / "my-skill" / "references" / "r.md").read_text() == "ref body"
