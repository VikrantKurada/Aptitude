from abc import ABC, abstractmethod
from aptitude.registry import Registry

provider_registry = Registry("provider")

class LLMProvider(ABC):
    name: str = "base"
    model: str = ""
    context_window: int = 8000

    @abstractmethod
    def generate(self, messages: list[dict], **opts) -> str: ...

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    @property
    def capabilities(self) -> set[str]:
        return {"chat"}
