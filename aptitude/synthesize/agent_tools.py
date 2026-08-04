# aptitude/synthesize/agent_tools.py
from pathlib import PurePosixPath
from aptitude.models import SkillFile, ToolSpec

TOOL_SPECS = [
    ToolSpec("list_sources", "List ingested sources with their titles and section headings.",
             {"type": "object", "properties": {}}),
    ToolSpec("read_source", "Read a source's text, optionally a single section by heading.",
             {"type": "object", "properties": {"index": {"type": "integer"},
              "section": {"type": "string"}}, "required": ["index"]}),
    ToolSpec("add_reference", "Save a distilled reference file for the final skill.",
             {"type": "object", "properties": {"relpath": {"type": "string"},
              "content": {"type": "string"}}, "required": ["relpath", "content"]}),
    ToolSpec("finish", "Finalize the skill.",
             {"type": "object", "properties": {"name": {"type": "string"},
              "description": {"type": "string"}, "body": {"type": "string"}},
             "required": ["name", "description", "body"]}),
]

class Toolbox:
    def __init__(self, docs, read_budget: int):
        self.docs = docs
        self.read_budget = read_budget
        self._read = 0
        self.references: list[SkillFile] = []

    def list_sources(self) -> str:
        lines = []
        for i, d in enumerate(self.docs):
            heads = ", ".join(s.heading for s in d.sections)
            lines.append(f"[{i}] {d.title} ({d.source.raw}) — sections: {heads}")
        return "\n".join(lines)

    def read_source(self, index: int, section: str | None = None) -> str:
        if self._read >= self.read_budget:
            return "read budget exhausted; use what you have and finish"
        try:
            doc = self.docs[int(index)]
        except (IndexError, ValueError, TypeError):
            return f"error: no source at index {index}"
        secs = [s for s in doc.sections if s.heading == section] if section else doc.sections
        if section and not secs:
            return f"error: no section '{section}' in source {index}"
        text = "\n\n".join(f"## {s.heading}\n{s.text}" for s in secs)
        remaining = self.read_budget - self._read
        text = text[: remaining * 4]              # ~4 chars/token cap
        self._read += max(1, len(text) // 4)
        return text

    def add_reference(self, relpath: str, content: str) -> str:
        norm = str(relpath).replace("\\", "/").strip()
        parts = PurePosixPath(norm).parts
        if not norm or norm.startswith("/") or PurePosixPath(norm).is_absolute() or ".." in parts:
            return f"error: invalid reference path '{relpath}' (must be a relative path without '..')"
        self.references.append(SkillFile(norm, content))
        return f"saved {norm}"

    def dispatch(self, name: str, arguments: dict) -> str:
        if not isinstance(arguments, dict):
            return "error: arguments must be an object"
        try:
            if name == "list_sources":
                return self.list_sources()
            if name == "read_source":
                return self.read_source(arguments["index"], arguments.get("section"))
            if name == "add_reference":
                return self.add_reference(arguments["relpath"], arguments["content"])
            return f"error: unknown tool '{name}'"
        except KeyError as e:
            return f"error: missing argument {e}"
