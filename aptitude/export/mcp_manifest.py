import json
from pathlib import Path
from aptitude.export.base import Exporter, export_registry

@export_registry.register("mcp-manifest")
class McpManifestExporter(Exporter):
    name = "mcp-manifest"
    def export(self, draft, out_dir) -> list[Path]:
        if not draft.tools:
            return []
        root = Path(out_dir) / draft.name; root.mkdir(parents=True, exist_ok=True)
        manifest = {"tools": [{"name": t.name, "description": t.description,
                               "parameters": t.parameters} for t in draft.tools]}
        p = root / "mcp.json"; p.write_text(json.dumps(manifest, indent=2))
        return [p]
