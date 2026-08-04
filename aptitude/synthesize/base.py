from abc import ABC, abstractmethod
from aptitude.registry import Registry
from aptitude.models import Document, SkillDraft

synth_registry = Registry("synth")

class Synthesizer(ABC):
    name: str = "base"
    @abstractmethod
    def synthesize(self, prompt: str, docs: list[Document], llm) -> SkillDraft: ...
