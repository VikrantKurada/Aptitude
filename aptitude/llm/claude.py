from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

def _build_claude_kwargs(model, messages, max_tokens=4096):
    sys = "\n".join(m["content"] for m in messages if m["role"] == "system")
    conv = [m for m in messages if m["role"] != "system"]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": conv}
    if sys:                      # only include system when non-empty
        kwargs["system"] = sys
    return kwargs

class _AnthropicClient:  # lazy real client
    def __init__(self, api_key):
        import anthropic
        self._c = anthropic.Anthropic(api_key=api_key)
    def generate(self, model, messages, **opts):
        kwargs = _build_claude_kwargs(model, messages, opts.get("max_tokens", 4096))
        resp = self._c.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

@provider_registry.register("claude")
class ClaudeProvider(LLMProvider):
    name = "claude"
    def __init__(self, model, api_key, client=None):
        self.model, self.context_window = model, 200000
        self._client = client or _AnthropicClient(api_key)
    def generate(self, messages, **opts) -> str:
        try:
            return self._client.generate(self.model, messages, **opts)
        except Exception as e:
            raise ProviderError(f"Claude call failed: {e}") from e
    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("claude", env)
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["claude"], key)
