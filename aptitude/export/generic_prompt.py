import json
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.models import SkillDraft

def _system_prompt(draft: SkillDraft) -> str:
    refs = "\n\n".join(f"# {f.relpath}\n{f.content}" for f in draft.references)
    parts = [draft.description, "", draft.body]
    if refs:
        parts += ["", "## Reference material", refs]
    return "\n".join(parts).strip()

@export_registry.register("generic-prompt")
class GenericPromptExporter(Exporter):
    name = "generic-prompt"
    def export(self, draft, out_dir) -> list[Path]:
        root = Path(out_dir) / draft.name; root.mkdir(parents=True, exist_ok=True)
        sysp = _system_prompt(draft)
        md = root / f"{draft.name}.md"; md.write_text(f"# {draft.name}\n\n{sysp}\n")
        js = root / f"{draft.name}.json"
        js.write_text(json.dumps({"name": draft.name, "description": draft.description,
                                  "system_prompt": sysp}, indent=2))
        return [md, js]
