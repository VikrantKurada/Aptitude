# aptitude/models.py
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["pdf", "epub", "web", "github", "auto"]

@dataclass
class Source:
    raw: str
    kind: Kind = "auto"

@dataclass
class Section:
    heading: str
    text: str
    code: str | None = None

@dataclass
class Document:
    source: Source
    title: str
    sections: list[Section]
    metadata: dict = field(default_factory=dict)

@dataclass
class Chunk:
    text: str
    token_count: int
    provenance: str

@dataclass
class SkillFile:
    relpath: str
    content: str

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)

@dataclass
class SkillDraft:
    name: str
    description: str
    body: str
    references: list[SkillFile] = field(default_factory=list)
    scripts: list[SkillFile] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
