import zipfile
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.export.claude_skill import ClaudeSkillExporter

@export_registry.register("zip")
class ZipPackager(Exporter):
    name = "zip"
    def export(self, draft, out_dir) -> list[Path]:
        out_dir = Path(out_dir)
        ClaudeSkillExporter().export(draft, out_dir)
        skill_dir = out_dir / draft.name
        zip_path = out_dir / f"{draft.name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in skill_dir.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(out_dir))
        return [zip_path]
