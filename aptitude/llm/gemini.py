from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

class _GeminiClient:
    def __init__(self, api_key):
        from google import genai
        self._c = genai.Client(api_key=api_key)
    def generate(self, model, messages, **opts):
        text = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        return self._c.models.generate_content(model=model, contents=text).text

@provider_registry.register("gemini")
class GeminiProvider(LLMProvider):
    name = "gemini"
    def __init__(self, model, api_key, client=None):
        self.model, self.context_window = model, 1000000
        self._client = client or _GeminiClient(api_key)
    def generate(self, messages, **opts) -> str:
        try:
            return self._client.generate(self.model, messages, **opts)
        except Exception as e:
            raise ProviderError(f"Gemini call failed: {e}") from e
    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("gemini", env)
        if not key:
            raise ProviderError("GEMINI_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["gemini"], key)
