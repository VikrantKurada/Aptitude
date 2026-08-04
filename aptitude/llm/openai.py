import json
import httpx
from aptitude.llm.base import LLMProvider, AssistantTurn, ToolCall, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

def _to_openai_tools(tools):
    return [{"type": "function", "function":
             {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]

def _to_openai_messages(messages):
    out = []
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            out.append({"role": "assistant", "content": m.get("content", "") or None,
                        "tool_calls": [{"id": c.id, "type": "function",
                                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                                       for c in m["tool_calls"]]})
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out

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

    @property
    def capabilities(self):
        return {"chat", "tools"}

    def chat(self, messages, tools) -> AssistantTurn:
        payload = {"model": self.model, "messages": _to_openai_messages(messages)}
        if tools:
            payload["tools"] = _to_openai_tools(tools)
        r = self._client.post(f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"}, json=payload)
        if r.status_code // 100 != 2:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:200]}")
        msg = r.json()["choices"][0]["message"]
        calls = [ToolCall(id=tc.get("id", f"call-{i}"), name=tc["function"]["name"],
                          arguments=json.loads(tc["function"]["arguments"] or "{}"))
                 for i, tc in enumerate(msg.get("tool_calls") or [])]
        return AssistantTurn(text=msg.get("content") or "", tool_calls=calls)

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
