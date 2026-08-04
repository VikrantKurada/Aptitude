import httpx
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"
    def __init__(self, model, api_key, base_url, context_window=8000, client=None):
        self.model, self.api_key = model, api_key
        self.base_url = base_url.rstrip("/")
        self.context_window = context_window
        self._client = client or httpx.Client(timeout=120)
    def generate(self, messages, **opts) -> str:
        r = self._client.post(f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, **opts})
        if r.status_code // 100 != 2:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"]

@provider_registry.register("openai")
class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["openai"],
                   api_key_for("openai", env),
                   cfg.get("base_url") or "https://api.openai.com/v1")

@provider_registry.register("nvidia")
class NvidiaProvider(OpenAICompatibleProvider):
    name = "nvidia"
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["nvidia"],
                   api_key_for("nvidia", env),
                   cfg.get("base_url") or "https://integrate.api.nvidia.com/v1")
