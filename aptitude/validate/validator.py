import re
from pathlib import Path
from aptitude.models import SkillDraft
from aptitude.errors import ValidationError

_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

def validate_draft(draft: SkillDraft) -> list[str]:
    if not _NAME.match(draft.name) or len(draft.name) > 64:
        raise ValidationError(f"invalid skill name '{draft.name}'")
    if not draft.description.strip():
        raise ValidationError("description must not be empty")
    if len(draft.description) > 1024:
        raise ValidationError("description exceeds 1024 chars")
    warnings = []
    if len(draft.body) < 40:
        warnings.append("body is very short; skill may be low quality")
    return warnings

def validate_skill_dir(path: Path) -> list[str]:
    skill = Path(path) / "SKILL.md"
    if not skill.exists():
        raise ValidationError(f"no SKILL.md in {path}")
    text = skill.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValidationError("SKILL.md missing YAML frontmatter")
    fm = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M))
    return validate_draft(SkillDraft(fm.get("name", ""), fm.get("description", ""),
                                     text[m.end():]))
