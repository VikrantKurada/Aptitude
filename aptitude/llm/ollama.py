import httpx
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import DEFAULT_MODELS

@provider_registry.register("ollama")
class OllamaProvider(LLMProvider):
    name = "ollama"
    def __init__(self, model, base_url="http://localhost:11434", client=None):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.context_window = 8000
        self._client = client or httpx.Client(timeout=300)
    def generate(self, messages, **opts) -> str:
        try:
            r = self._client.post(f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False})
        except Exception as e:
            raise ProviderError(f"Ollama unreachable at {self.base_url}: {e}") from e
        if r.status_code // 100 != 2:
            raise ProviderError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["message"]["content"]
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["ollama"],
                   cfg.get("base_url") or "http://localhost:11434")
