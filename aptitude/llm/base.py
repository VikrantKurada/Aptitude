from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from aptitude.registry import Registry

provider_registry = Registry("provider")

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)

@dataclass
class AssistantTurn:
    text: str
    tool_calls: list = field(default_factory=list)

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

    def chat(self, messages: list[dict], tools: list) -> "AssistantTurn":
        from aptitude.llm import tools_react
        prose, calls = tools_react.parse_action(
            self.generate([{"role": "user", "content": tools_react.render_prompt(messages, tools)}])
        )
        return AssistantTurn(text=prose.strip(), tool_calls=calls)
