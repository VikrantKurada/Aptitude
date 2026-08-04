import httpx
from aptitude.llm.base import LLMProvider, AssistantTurn, ToolCall, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import DEFAULT_MODELS

def _to_ollama_messages(messages):
    out = []
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            out.append({"role": "assistant", "content": m.get("content", ""),
                        "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}}
                                       for c in m["tool_calls"]]})
        elif m["role"] == "tool":
            out.append({"role": "tool", "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out

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
    @property
    def capabilities(self):
        return {"chat", "tools"}
    def chat(self, messages, tools) -> AssistantTurn:
        payload = {"model": self.model, "messages": _to_ollama_messages(messages), "stream": False}
        if tools:
            payload["tools"] = [{"type": "function", "function":
                                 {"name": t.name, "description": t.description, "parameters": t.parameters}}
                                for t in tools]
        try:
            r = self._client.post(f"{self.base_url}/api/chat", json=payload)
        except Exception as e:
            raise ProviderError(f"Ollama unreachable at {self.base_url}: {e}") from e
        if r.status_code // 100 != 2:
            raise ProviderError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        msg = r.json()["message"]
        calls = [ToolCall(id=f"call-{i}", name=tc["function"]["name"],
                          arguments=tc["function"].get("arguments") or {})
                 for i, tc in enumerate(msg.get("tool_calls") or [])]
        return AssistantTurn(text=msg.get("content") or "", tool_calls=calls)
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["ollama"],
                   cfg.get("base_url") or "http://localhost:11434")
