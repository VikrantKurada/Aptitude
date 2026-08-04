from aptitude.llm.base import LLMProvider, AssistantTurn, ToolCall, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

def _build_claude_kwargs(model, messages, max_tokens=4096):
    sys = "\n".join(m["content"] for m in messages if m["role"] == "system")
    conv = [m for m in messages if m["role"] != "system"]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": conv}
    if sys:                      # only include system when non-empty
        kwargs["system"] = sys
    return kwargs

def _to_anthropic(messages):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system") or None
    blocks = []
    for m in messages:
        if m["role"] == "system":
            continue
        if m["role"] == "assistant" and m.get("tool_calls"):
            content = ([{"type": "text", "text": m["content"]}] if m.get("content") else []) + \
                      [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                       for c in m["tool_calls"]]
            blocks.append({"role": "assistant", "content": content})
        elif m["role"] == "tool":
            blocks.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}]})
        else:
            blocks.append({"role": m["role"], "content": m["content"]})
    return system, blocks

class _AnthropicClient:  # lazy real client
    def __init__(self, api_key):
        import anthropic
        self._c = anthropic.Anthropic(api_key=api_key)
    def generate(self, model, messages, **opts):
        kwargs = _build_claude_kwargs(model, messages, opts.get("max_tokens", 4096))
        resp = self._c.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    def chat(self, model, messages, tools, max_tokens=4096):
        system, blocks = _to_anthropic(messages)
        schema = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        resp = self._c.messages.create(model=model, max_tokens=max_tokens,
                                       system=system, messages=blocks, tools=schema or None)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        calls = [ToolCall(id=b.id, name=b.name, arguments=b.input)
                 for b in resp.content if getattr(b, "type", "") == "tool_use"]
        return text, calls

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
    @property
    def capabilities(self):
        return {"chat", "tools"}
    def chat(self, messages, tools) -> AssistantTurn:
        try:
            text, calls = self._client.chat(self.model, messages, tools)
        except Exception as e:
            raise ProviderError(f"Claude chat failed: {e}") from e
        return AssistantTurn(text=text, tool_calls=calls)
    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("claude", env)
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["claude"], key)
