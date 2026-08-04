from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.models import SkillDraft

def _yaml_escape(v: str) -> str:
    return v.replace("\n", " ").strip()

@export_registry.register("claude-skill")
class ClaudeSkillExporter(Exporter):
    name = "claude-skill"
    def export(self, draft: SkillDraft, out_dir: Path) -> list[Path]:
        root = Path(out_dir) / draft.name
        root.mkdir(parents=True, exist_ok=True)
        fm = (f"---\nname: {draft.name}\n"
              f"description: {_yaml_escape(draft.description)}\n---\n\n")
        skill_md = root / "SKILL.md"
        skill_md.write_text(fm + draft.body + "\n")
        written = [skill_md]
        for f in [*draft.references, *draft.scripts]:
            fp = root / f.relpath
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(f.content)
            written.append(fp)
        return written
