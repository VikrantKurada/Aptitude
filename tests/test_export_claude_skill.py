from aptitude.models import SkillDraft, SkillFile
from aptitude.export.claude_skill import ClaudeSkillExporter
from tests.export_contract import assert_exporter_contract

def _draft():
    return SkillDraft(name="my-skill", description="Use when testing.",
                      body="## Steps\nDo it.",
                      references=[SkillFile("references/r.md", "ref body")])

def test_claude_skill_layout(tmp_path):
    paths = assert_exporter_contract(ClaudeSkillExporter(), _draft(), tmp_path)
    skill_md = (tmp_path / "my-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert skill_md.startswith("---\n")
    assert "name: my-skill" in skill_md and 'description: "Use when testing."' in skill_md
    assert "## Steps" in skill_md
    assert (tmp_path / "my-skill" / "references" / "r.md").read_text(encoding="utf-8") == "ref body"


def test_export_roundtrips_non_ascii(tmp_path):
    from aptitude.models import SkillDraft, SkillFile
    from aptitude.export.claude_skill import ClaudeSkillExporter
    draft = SkillDraft(name="unicode-skill",
                       description="Use when drafting with arrows → and checks ✓",
                       body="Body with ≤, ×, café, Ω and 中文.",
                       references=[SkillFile("references/r.md", "Réf: ≥ 5 items ✓")])
    ClaudeSkillExporter().export(draft, tmp_path)
    text = (tmp_path / "unicode-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "→" in text and "≤" in text and "中文" in text
    assert (tmp_path / "unicode-skill" / "references" / "r.md").read_text(encoding="utf-8") == "Réf: ≥ 5 items ✓"


def test_description_with_colon_is_valid_yaml_scalar(tmp_path):
    import json
    from aptitude.models import SkillDraft
    from aptitude.export.claude_skill import ClaudeSkillExporter
    desc = "Use when the user wants to: draft GDPR policies"
    ClaudeSkillExporter().export(SkillDraft("s", desc, "body"), tmp_path)
    skill = (tmp_path / "s" / "SKILL.md").read_text(encoding="utf-8")
    # extract the description line's value and confirm it's a valid quoted scalar round-tripping to the original
    line = next(l for l in skill.splitlines() if l.startswith("description:"))
    value = line[len("description:"):].strip()
    assert json.loads(value) == desc      # valid quoted scalar, no data loss
