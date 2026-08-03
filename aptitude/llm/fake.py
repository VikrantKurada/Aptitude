from aptitude.llm.base import LLMProvider, provider_registry

@provider_registry.register("fake")
class FakeProvider(LLMProvider):
    name = "fake"
    def __init__(self, model="fake", context_window=8000, responses=None, echo=True):
        self.model, self.context_window = model, context_window
        self._responses = list(responses or [])
        self._echo = echo
    def generate(self, messages, **opts) -> str:
        if self._responses:
            return self._responses.pop(0)
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"[fake] {last[:200]}" if self._echo else "[fake]"
