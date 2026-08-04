from abc import ABC, abstractmethod
from pathlib import Path
from aptitude.registry import Registry
from aptitude.models import SkillDraft

export_registry = Registry("exporter")

class Exporter(ABC):
    name: str = "base"
    @abstractmethod
    def export(self, draft: SkillDraft, out_dir: Path) -> list[Path]: ...
