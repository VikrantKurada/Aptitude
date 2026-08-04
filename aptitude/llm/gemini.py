from aptitude.llm.base import LLMProvider, AssistantTurn, ToolCall, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

def _to_gemini_contents(messages):
    contents = []
    for m in messages:
        if m["role"] == "system":
            contents.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant" and m.get("tool_calls"):
            parts = [{"functionCall": {"name": c.name, "args": c.arguments}} for c in m["tool_calls"]]
            if m.get("content"):
                parts = [{"text": m["content"]}] + parts
            contents.append({"role": "model", "parts": parts})
        elif m["role"] == "tool":
            contents.append({"role": "user", "parts": [
                {"functionResponse": {"name": m["name"], "response": {"result": m["content"]}}}]})
        else:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    return contents

class _GeminiClient:
    def __init__(self, api_key):
        from google import genai
        self._c = genai.Client(api_key=api_key)
    def generate(self, model, messages, **opts):
        text = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        return self._c.models.generate_content(model=model, contents=text).text or ""
    def chat(self, model, messages, tools):
        decls = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]
        resp = self._c.models.generate_content(
            model=model, contents=_to_gemini_contents(messages),
            config={"tools": [{"function_declarations": decls}]} if decls else None)
        text, calls = "", []
        for cand in getattr(resp, "candidates", []) or []:
            for part in getattr(cand.content, "parts", []) or []:
                fc = getattr(part, "function_call", None)
                if fc:
                    args = getattr(fc, "args", None)
                    calls.append(ToolCall(id=f"fc-{len(calls)}", name=fc.name, arguments=dict(args) if args else {}))
                elif getattr(part, "text", None):
                    text += part.text
        return text, calls

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
    @property
    def capabilities(self):
        return {"chat", "tools"}
    def chat(self, messages, tools) -> AssistantTurn:
        try:
            text, calls = self._client.chat(self.model, messages, tools)
        except Exception as e:
            raise ProviderError(f"Gemini chat failed: {e}") from e
        return AssistantTurn(text=text, tool_calls=calls)
    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("gemini", env)
        if not key:
            raise ProviderError("GEMINI_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["gemini"], key)
