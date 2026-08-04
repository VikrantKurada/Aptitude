from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.export.generic_prompt import _system_prompt

@export_registry.register("local-llm")
class LocalLlmExporter(Exporter):
    name = "local-llm"
    def export(self, draft, out_dir) -> list[Path]:
        root = Path(out_dir) / draft.name; root.mkdir(parents=True, exist_ok=True)
        sysp = _system_prompt(draft)
        mf = root / "Modelfile"
        mf.write_text(f'FROM llama3.1\nSYSTEM """\n{sysp}\n"""\n')
        st = root / "system.txt"; st.write_text(sysp + "\n")
        return [mf, st]
