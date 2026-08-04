import json
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.models import SkillDraft

def _yaml_scalar(v: str) -> str:
    # A JSON string is a valid double-quoted YAML scalar. Use ensure_ascii=False
    # so non-ASCII content (the file is written as UTF-8) stays human-readable
    # instead of being escaped to \uXXXX sequences.
    return json.dumps(" ".join(v.split()), ensure_ascii=False)

@export_registry.register("claude-skill")
class ClaudeSkillExporter(Exporter):
    name = "claude-skill"
    def export(self, draft: SkillDraft, out_dir: Path) -> list[Path]:
        root = Path(out_dir) / draft.name
        root.mkdir(parents=True, exist_ok=True)
        fm = (f"---\nname: {draft.name}\n"
              f"description: {_yaml_scalar(draft.description)}\n---\n\n")
        skill_md = root / "SKILL.md"
        skill_md.write_text(fm + draft.body + "\n", encoding="utf-8")
        written = [skill_md]
        for f in [*draft.references, *draft.scripts]:
            fp = root / f.relpath
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(f.content, encoding="utf-8")
            written.append(fp)
        return written
