# Agentic Synthesizer (V2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `agentic` synthesizer that builds a skill via an LLM agent loop with tools, producing the same `SkillDraft` as `template`.

**Architecture:** Extend `LLMProvider` with a tool-aware `chat(messages, tools) -> AssistantTurn` whose default is a ReAct text protocol; each provider overrides it with native tool-calling. A new `AgenticSynthesizer` runs a bounded agent loop (explore → draft → forced self-critique → finish) over four in-memory tools, falling back to `TemplateSynthesizer` on non-convergence.

**Tech Stack:** Python 3.11+, existing deps only (httpx, stdlib `json`/`dataclasses`/`re`), pytest with `httpx.MockTransport` and injected fake clients — no network in the default suite.

## Global Constraints

- Python `>=3.11`. All file I/O already uses `encoding="utf-8"`; keep that.
- **Additive & backward-compatible:** `template` stays the default synthesizer; do not change existing synthesizer/exporter/ingest behavior.
- Reuse existing types: `ToolSpec(name, description, parameters)` from `aptitude.models`; `SkillDraft`/`SkillFile`; `TemplateSynthesizer._slug`.
- Neutral message shapes (the only format the agent loop speaks): `{"role":"system","content":str}`, `{"role":"user","content":str}`, `{"role":"assistant","content":str,"tool_calls":[ToolCall]}`, `{"role":"tool","tool_call_id":str,"name":str,"content":str}`.
- `ToolCall.arguments` is always a Python `dict` (normalize JSON strings).
- No filesystem/network tools for the agent — `read_source` serves only ingested `docs`; `add_reference` accumulates in memory.
- TDD: failing test first, watch it fail, minimal implementation, watch it pass, commit.
- No network in the default suite; live provider calls stay behind `@pytest.mark.live`.
- Tests live under `tests/`; `tests/` and `tests/fixtures/` are packages (`__init__.py` exist).

---

## File Structure

| Path | Responsibility |
|---|---|
| `aptitude/llm/base.py` | + `ToolCall`, `AssistantTurn`; + `chat()` ReAct default; + `count_tokens` unchanged |
| `aptitude/llm/tools_react.py` | ReAct render (neutral→prompt) + parse (text→ToolCall) helpers |
| `aptitude/llm/openai.py` | + native `chat()` for `openai`/`nvidia`; + `"tools"` capability |
| `aptitude/llm/claude.py` | + native `chat()`; extend client seam; + capability |
| `aptitude/llm/gemini.py` | + native `chat()`; extend client seam; + capability |
| `aptitude/llm/ollama.py` | + native `chat()`; + capability |
| `aptitude/synthesize/agent_tools.py` | The four tools (ToolSpecs + impls) bound to docs + read budget |
| `aptitude/synthesize/agent_prompts.py` | System prompt + critique instruction |
| `aptitude/synthesize/agentic.py` | `AgenticSynthesizer` + `_SkillAgent` loop + fallback |
| `aptitude/cli.py` | + `--synth`, `--max-iterations`; `providers` shows `tools` |
| `aptitude/config.py` | + `synth` in DEFAULTS / `APTITUDE_SYNTH` |
| `README.md` | + "Synthesizers" section |

---

## Task 1: Tool types + ReAct default `chat()`

**Files:**
- Modify: `aptitude/llm/base.py`
- Create: `aptitude/llm/tools_react.py`
- Modify: `tests/llm_contract.py`
- Test: `tests/test_tools_react.py`

**Interfaces:**
- Consumes: `ToolSpec` (aptitude.models), `FakeProvider` (Task exists), `provider_registry`.
- Produces: `ToolCall(id:str, name:str, arguments:dict)`, `AssistantTurn(text:str, tool_calls:list[ToolCall])` in `aptitude.llm.base`. `LLMProvider.chat(messages:list[dict], tools:list[ToolSpec]) -> AssistantTurn` (ReAct default). `tools_react.render_prompt(messages, tools) -> str` and `tools_react.parse_action(text) -> tuple[str, list[ToolCall]]` (returns `(prose, tool_calls)`). Contract helper `assert_chat_contract(provider)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools_react.py
from aptitude.models import ToolSpec
from aptitude.llm.base import ToolCall, AssistantTurn
from aptitude.llm import tools_react
from aptitude.llm.fake import FakeProvider

TOOLS = [ToolSpec("read_source", "read a source", {"type": "object"})]

def test_parse_action_extracts_tool_call():
    text = 'Let me read it.\n```action\n{"tool": "read_source", "arguments": {"index": 0}}\n```'
    prose, calls = tools_react.parse_action(text)
    assert prose.strip() == "Let me read it."
    assert calls and calls[0].name == "read_source" and calls[0].arguments == {"index": 0}

def test_parse_action_plain_text_no_calls():
    prose, calls = tools_react.parse_action("just talking, no action")
    assert calls == [] and prose == "just talking, no action"

def test_parse_action_malformed_block_no_calls():
    prose, calls = tools_react.parse_action('```action\n{not json]\n```')
    assert calls == []

def test_fake_provider_chat_returns_assistant_turn():
    p = FakeProvider(responses=['```action\n{"tool":"read_source","arguments":{"index":1}}\n```'])
    turn = p.chat([{"role": "user", "content": "go"}], TOOLS)
    assert isinstance(turn, AssistantTurn)
    assert turn.tool_calls[0].name == "read_source" and turn.tool_calls[0].arguments == {"index": 1}

def test_fake_provider_chat_no_tools_is_plain_text():
    p = FakeProvider(responses=["final answer"])
    turn = p.chat([{"role": "user", "content": "hi"}], [])
    assert turn.text == "final answer" and turn.tool_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools_react.py -v`
Expected: FAIL — `ImportError` (`tools_react` / `ToolCall` don't exist).

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/llm/tools_react.py
import json
import re
from aptitude.llm.base import ToolCall

_ACTION_RE = re.compile(r"```action\s*(\{.*?\})\s*```", re.S)

def render_prompt(messages, tools) -> str:
    catalog = "\n".join(
        f"- {t.name}: {t.description} | parameters: {json.dumps(t.parameters)}" for t in tools
    )
    lines = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            for c in m["tool_calls"]:
                lines.append(f'ASSISTANT ACTION: {c.name}({json.dumps(c.arguments)})')
            if m.get("content"):
                lines.append(f"ASSISTANT: {m['content']}")
        elif role == "tool":
            lines.append(f"OBSERVATION ({m.get('name','')}): {m['content']}")
        else:
            lines.append(f"{role.upper()}: {m['content']}")
    transcript = "\n".join(lines)
    guide = (
        "You can call ONE tool per turn by emitting a fenced block:\n"
        '```action\n{"tool": "<name>", "arguments": {...}}\n```\n'
        "Emit an action block to use a tool, or plain text when you are done."
    )
    header = f"AVAILABLE TOOLS:\n{catalog}\n\n{guide}\n\n" if tools else ""
    return f"{header}CONVERSATION:\n{transcript}"

def parse_action(text: str):
    m = _ACTION_RE.search(text)
    if not m:
        return text, []
    prose = text[: m.start()]
    try:
        data = json.loads(m.group(1))
        name = data["tool"]
        args = data.get("arguments", {})
        if not isinstance(args, dict):
            return prose, []
    except (ValueError, KeyError, TypeError):
        return prose, []
    return prose, [ToolCall(id="react-0", name=name, arguments=args)]
```

Add to `aptitude/llm/base.py` (after the existing imports; keep everything else):

```python
from dataclasses import dataclass, field

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)

@dataclass
class AssistantTurn:
    text: str
    tool_calls: list = field(default_factory=list)
```

And add the `chat` method to `LLMProvider`:

```python
    def chat(self, messages: list[dict], tools: list) -> "AssistantTurn":
        from aptitude.llm import tools_react
        prose, calls = tools_react.parse_action(
            self.generate([{"role": "user", "content": tools_react.render_prompt(messages, tools)}])
        )
        return AssistantTurn(text=prose.strip(), tool_calls=calls)
```

Append to `tests/llm_contract.py`:

```python
def assert_chat_contract(provider):
    from aptitude.models import ToolSpec
    turn = provider.chat([{"role": "user", "content": "hello"}], [])
    assert isinstance(turn.text, str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools_react.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/base.py aptitude/llm/tools_react.py tests/llm_contract.py tests/test_tools_react.py
git commit -m "feat: ToolCall/AssistantTurn + ReAct-default chat() on LLMProvider"
```

---

## Task 2: Native `chat()` for OpenAI-compatible (openai + nvidia)

**Files:**
- Modify: `aptitude/llm/openai.py`
- Test: `tests/test_llm_openai_tools.py`

**Interfaces:**
- Consumes: `ToolCall`/`AssistantTurn` (Task 1), `ToolSpec`, `OpenAICompatibleProvider` (existing, has injectable `client`).
- Produces: `OpenAICompatibleProvider.chat(messages, tools) -> AssistantTurn` (native); `capabilities` includes `"tools"`. Module helper `_to_openai_messages(neutral) -> list[dict]` and `_to_openai_tools(tools) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_openai_tools.py
import httpx, json
from aptitude.models import ToolSpec
from aptitude.llm.openai import OpenAICompatibleProvider, _to_openai_messages

TOOLS = [ToolSpec("read_source", "read", {"type": "object", "properties": {"index": {"type": "integer"}}})]

def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_chat_parses_tool_call():
    def handler(req):
        body = json.loads(req.content)
        assert body["tools"][0]["type"] == "function"          # tools sent natively
        return httpx.Response(200, json={"choices": [{"message": {
            "content": "reading", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "read_source", "arguments": "{\"index\": 2}"}}]}}]})
    p = OpenAICompatibleProvider("m", "k", "https://x/v1", client=_client(handler))
    turn = p.chat([{"role": "user", "content": "go"}], TOOLS)
    assert turn.text == "reading"
    assert turn.tool_calls[0].name == "read_source"
    assert turn.tool_calls[0].arguments == {"index": 2}        # JSON string normalized to dict
    assert "tools" in p.capabilities

def test_tool_result_message_roundtrips():
    msgs = [{"role": "assistant", "content": "", "tool_calls":
             [__import__("aptitude.llm.base", fromlist=["ToolCall"]).ToolCall("call_1", "read_source", {"index": 2})]},
            {"role": "tool", "tool_call_id": "call_1", "name": "read_source", "content": "the text"}]
    out = _to_openai_messages(msgs)
    assert out[0]["tool_calls"][0]["id"] == "call_1"
    assert out[1]["role"] == "tool" and out[1]["tool_call_id"] == "call_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_openai_tools.py -v`
Expected: FAIL — `_to_openai_messages` / `chat` not present.

- [ ] **Step 3: Write minimal implementation**

Add to `aptitude/llm/openai.py` (module-level helpers + method on `OpenAICompatibleProvider`; keep existing `generate`):

```python
import json
from aptitude.llm.base import AssistantTurn, ToolCall

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
```

Add the method (inside `OpenAICompatibleProvider`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_openai_tools.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/openai.py tests/test_llm_openai_tools.py
git commit -m "feat: native tool-calling chat() for OpenAI-compatible providers"
```

---

## Task 3: Native `chat()` for Claude

**Files:**
- Modify: `aptitude/llm/claude.py`
- Test: `tests/test_llm_claude_tools.py`

**Interfaces:**
- Consumes: `ToolCall`/`AssistantTurn`, `ToolSpec`, existing `ClaudeProvider` (injectable `client` with a `.generate(...)` seam).
- Produces: `ClaudeProvider.chat(messages, tools) -> AssistantTurn`; the injected client gains a `.chat(model, messages, tools) -> (text, list[ToolCall])` seam so tests avoid the SDK; `capabilities` includes `"tools"`. Module helper `_to_anthropic(messages) -> tuple[str|None, list[dict]]` (system, message blocks).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_claude_tools.py
from aptitude.models import ToolSpec
from aptitude.llm.base import ToolCall, AssistantTurn
from aptitude.llm.claude import ClaudeProvider, _to_anthropic

TOOLS = [ToolSpec("finish", "finish", {"type": "object"})]

class _FakeClient:
    def chat(self, model, messages, tools):
        return ("thinking", [ToolCall("tu_1", "finish", {"name": "x"})])
    def generate(self, model, messages, **o): return "plain"

def test_claude_chat_returns_toolcalls():
    turn = ClaudeProvider("m", "k", client=_FakeClient()).chat([{"role": "user", "content": "go"}], TOOLS)
    assert isinstance(turn, AssistantTurn)
    assert turn.text == "thinking" and turn.tool_calls[0].name == "finish"
    assert "tools" in ClaudeProvider("m", "k", client=_FakeClient()).capabilities

def test_to_anthropic_splits_system_and_tool_blocks():
    sys, blocks = _to_anthropic([
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("tu_1", "finish", {"a": 1})]},
        {"role": "tool", "tool_call_id": "tu_1", "name": "finish", "content": "ok"}])
    assert sys == "S"
    assert blocks[0]["role"] == "user"
    assert any(b["role"] == "assistant" for b in blocks)
    # the tool result is a user message carrying a tool_result content block
    tr = [b for b in blocks if b["role"] == "user" and isinstance(b["content"], list)][ -1]
    assert tr["content"][0]["type"] == "tool_result" and tr["content"][0]["tool_use_id"] == "tu_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_claude_tools.py -v`
Expected: FAIL — `_to_anthropic` / `chat` missing.

- [ ] **Step 3: Write minimal implementation**

Add to `aptitude/llm/claude.py` (module helper + real-client method + provider method; keep existing `generate`):

```python
from aptitude.llm.base import AssistantTurn, ToolCall

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
```

Extend `_AnthropicClient` with a `chat` method:

```python
    def chat(self, model, messages, tools, max_tokens=4096):
        system, blocks = _to_anthropic(messages)
        schema = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        resp = self._c.messages.create(model=model, max_tokens=max_tokens,
                                       system=system, messages=blocks, tools=schema or None)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        calls = [ToolCall(id=b.id, name=b.name, arguments=b.input)
                 for b in resp.content if getattr(b, "type", "") == "tool_use"]
        return text, calls
```

Add to `ClaudeProvider`:

```python
    @property
    def capabilities(self):
        return {"chat", "tools"}

    def chat(self, messages, tools) -> AssistantTurn:
        try:
            text, calls = self._client.chat(self.model, messages, tools)
        except Exception as e:
            raise ProviderError(f"Claude chat failed: {e}") from e
        return AssistantTurn(text=text, tool_calls=calls)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_claude_tools.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/claude.py tests/test_llm_claude_tools.py
git commit -m "feat: native tool-calling chat() for Claude"
```

**IMPLEMENTER NOTE:** confirm the Anthropic tools request/response shape (`tools` param, `tool_use`/`tool_result` blocks) against the `claude-api` skill before finalizing.

---

## Task 4: Native `chat()` for Gemini

**Files:**
- Modify: `aptitude/llm/gemini.py`
- Test: `tests/test_llm_gemini_tools.py`

**Interfaces:**
- Consumes: `ToolCall`/`AssistantTurn`, `ToolSpec`, existing `GeminiProvider` (injectable client with `.generate`).
- Produces: `GeminiProvider.chat(messages, tools) -> AssistantTurn`; injected client gains `.chat(model, messages, tools) -> (text, list[ToolCall])`; `capabilities` includes `"tools"`; helper `_to_gemini_contents(messages) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_gemini_tools.py
from aptitude.models import ToolSpec
from aptitude.llm.base import ToolCall, AssistantTurn
from aptitude.llm.gemini import GeminiProvider, _to_gemini_contents

TOOLS = [ToolSpec("read_source", "read", {"type": "object"})]

class _FakeClient:
    def chat(self, model, messages, tools):
        return ("", [ToolCall("fc-0", "read_source", {"index": 0})])
    def generate(self, model, messages, **o): return "x"

def test_gemini_chat_returns_toolcalls():
    turn = GeminiProvider("m", "k", client=_FakeClient()).chat([{"role": "user", "content": "go"}], TOOLS)
    assert isinstance(turn, AssistantTurn)
    assert turn.tool_calls[0].name == "read_source" and turn.tool_calls[0].arguments == {"index": 0}
    assert "tools" in GeminiProvider("m", "k", client=_FakeClient()).capabilities

def test_to_gemini_contents_maps_roles_and_tool_parts():
    contents = _to_gemini_contents([
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("fc-0", "read_source", {"index": 0})]},
        {"role": "tool", "tool_call_id": "fc-0", "name": "read_source", "content": "text"}])
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["functionCall"]["name"] == "read_source"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "read_source"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_gemini_tools.py -v`
Expected: FAIL — `_to_gemini_contents` / `chat` missing.

- [ ] **Step 3: Write minimal implementation**

Add to `aptitude/llm/gemini.py`:

```python
from aptitude.llm.base import AssistantTurn, ToolCall

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
```

Extend `_GeminiClient` with `chat`:

```python
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
                    calls.append(ToolCall(id=f"fc-{len(calls)}", name=fc.name, arguments=dict(fc.args or {})))
                elif getattr(part, "text", None):
                    text += part.text
        return text, calls
```

Add to `GeminiProvider`:

```python
    @property
    def capabilities(self):
        return {"chat", "tools"}

    def chat(self, messages, tools) -> AssistantTurn:
        try:
            text, calls = self._client.chat(self.model, messages, tools)
        except Exception as e:
            raise ProviderError(f"Gemini chat failed: {e}") from e
        return AssistantTurn(text=text, tool_calls=calls)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_gemini_tools.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/gemini.py tests/test_llm_gemini_tools.py
git commit -m "feat: native tool-calling chat() for Gemini"
```

---

## Task 5: Native `chat()` for Ollama

**Files:**
- Modify: `aptitude/llm/ollama.py`
- Test: `tests/test_llm_ollama_tools.py`

**Interfaces:**
- Consumes: `ToolCall`/`AssistantTurn`, `ToolSpec`, existing `OllamaProvider` (injectable httpx client).
- Produces: `OllamaProvider.chat(messages, tools) -> AssistantTurn`; `capabilities` includes `"tools"`; helper `_to_ollama_messages(messages) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_ollama_tools.py
import httpx, json
from aptitude.models import ToolSpec
from aptitude.llm.ollama import OllamaProvider, _to_ollama_messages
from aptitude.llm.base import ToolCall

TOOLS = [ToolSpec("read_source", "read", {"type": "object"})]

def test_ollama_chat_parses_tool_calls():
    def handler(req):
        body = json.loads(req.content)
        assert body["tools"][0]["function"]["name"] == "read_source"
        return httpx.Response(200, json={"message": {"content": "",
            "tool_calls": [{"function": {"name": "read_source", "arguments": {"index": 3}}}]}})
    p = OllamaProvider("m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    turn = p.chat([{"role": "user", "content": "go"}], TOOLS)
    assert turn.tool_calls[0].name == "read_source" and turn.tool_calls[0].arguments == {"index": 3}
    assert "tools" in p.capabilities

def test_to_ollama_messages_roundtrips_tool_result():
    out = _to_ollama_messages([
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("c1", "read_source", {"index": 3})]},
        {"role": "tool", "tool_call_id": "c1", "name": "read_source", "content": "text"}])
    assert out[0]["tool_calls"][0]["function"]["name"] == "read_source"
    assert out[1]["role"] == "tool" and out[1]["content"] == "text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_ollama_tools.py -v`
Expected: FAIL — `_to_ollama_messages` / `chat` missing.

- [ ] **Step 3: Write minimal implementation**

Add to `aptitude/llm/ollama.py`:

```python
from aptitude.llm.base import AssistantTurn, ToolCall

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
```

Add to `OllamaProvider`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_ollama_tools.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/ollama.py tests/test_llm_ollama_tools.py
git commit -m "feat: native tool-calling chat() for Ollama"
```

---

## Task 6: Agent tools (list_sources / read_source / add_reference / finish)

**Files:**
- Create: `aptitude/synthesize/agent_tools.py`
- Test: `tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `Document`/`Section`/`SkillFile`/`ToolSpec` (aptitude.models).
- Produces: `TOOL_SPECS: list[ToolSpec]` (the four tools' schemas). `Toolbox(docs, read_budget:int)` with methods `list_sources() -> str`, `read_source(index:int, section:str|None=None) -> str` (truncates each read; returns a "read budget exhausted" notice once cumulative chars exceed `read_budget`), `add_reference(relpath:str, content:str) -> str`, and attribute `references: list[SkillFile]`. `Toolbox.dispatch(name:str, arguments:dict) -> str` routes a tool call (unknown tool / bad args → returns an error string, never raises). `finish` is NOT dispatched here (handled by the loop).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_tools.py
from aptitude.models import Document, Source, Section
from aptitude.synthesize.agent_tools import Toolbox, TOOL_SPECS

def _docs():
    return [Document(Source("a.pdf"), "DocA", [Section("Intro", "alpha "*10), Section("Body", "beta "*10)]),
            Document(Source("b.md"), "DocB", [Section("H", "gamma "*10)])]

def test_tool_specs_present():
    names = {t.name for t in TOOL_SPECS}
    assert {"list_sources", "read_source", "add_reference", "finish"} <= names

def test_list_sources_lists_titles_and_headings():
    out = Toolbox(_docs(), read_budget=10000).list_sources()
    assert "DocA" in out and "Intro" in out and "DocB" in out

def test_read_source_returns_section_text():
    tb = Toolbox(_docs(), read_budget=10000)
    assert "beta" in tb.read_source(0, section="Body")
    assert "alpha" in tb.read_source(0)          # whole doc when no section

def test_read_budget_exhaustion():
    tb = Toolbox(_docs(), read_budget=20)         # tiny budget
    tb.read_source(0)                             # consumes it
    assert "budget" in tb.read_source(1).lower()  # exhausted notice

def test_add_reference_accumulates():
    tb = Toolbox(_docs(), read_budget=10000)
    tb.add_reference("references/r.md", "distilled")
    assert tb.references[0].relpath == "references/r.md" and tb.references[0].content == "distilled"

def test_dispatch_unknown_tool_returns_error_not_raise():
    out = Toolbox(_docs(), read_budget=10000).dispatch("nope", {})
    assert "error" in out.lower() or "unknown" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_tools.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/synthesize/agent_tools.py
from aptitude.models import SkillFile, ToolSpec

TOOL_SPECS = [
    ToolSpec("list_sources", "List ingested sources with their titles and section headings.",
             {"type": "object", "properties": {}}),
    ToolSpec("read_source", "Read a source's text, optionally a single section by heading.",
             {"type": "object", "properties": {"index": {"type": "integer"},
              "section": {"type": "string"}}, "required": ["index"]}),
    ToolSpec("add_reference", "Save a distilled reference file for the final skill.",
             {"type": "object", "properties": {"relpath": {"type": "string"},
              "content": {"type": "string"}}, "required": ["relpath", "content"]}),
    ToolSpec("finish", "Finalize the skill.",
             {"type": "object", "properties": {"name": {"type": "string"},
              "description": {"type": "string"}, "body": {"type": "string"}},
             "required": ["name", "description", "body"]}),
]

class Toolbox:
    def __init__(self, docs, read_budget: int):
        self.docs = docs
        self.read_budget = read_budget
        self._read = 0
        self.references: list[SkillFile] = []

    def list_sources(self) -> str:
        lines = []
        for i, d in enumerate(self.docs):
            heads = ", ".join(s.heading for s in d.sections)
            lines.append(f"[{i}] {d.title} ({d.source.raw}) — sections: {heads}")
        return "\n".join(lines)

    def read_source(self, index: int, section: str | None = None) -> str:
        if self._read >= self.read_budget:
            return "read budget exhausted; use what you have and finish"
        try:
            doc = self.docs[int(index)]
        except (IndexError, ValueError, TypeError):
            return f"error: no source at index {index}"
        secs = [s for s in doc.sections if s.heading == section] if section else doc.sections
        if section and not secs:
            return f"error: no section '{section}' in source {index}"
        text = "\n\n".join(f"## {s.heading}\n{s.text}" for s in secs)
        remaining = self.read_budget - self._read
        text = text[: remaining * 4]              # ~4 chars/token cap
        self._read += max(1, len(text) // 4)
        return text

    def add_reference(self, relpath: str, content: str) -> str:
        self.references.append(SkillFile(relpath, content))
        return f"saved {relpath}"

    def dispatch(self, name: str, arguments: dict) -> str:
        try:
            if name == "list_sources":
                return self.list_sources()
            if name == "read_source":
                return self.read_source(arguments.get("index"), arguments.get("section"))
            if name == "add_reference":
                return self.add_reference(arguments["relpath"], arguments["content"])
            return f"error: unknown tool '{name}'"
        except KeyError as e:
            return f"error: missing argument {e}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_tools.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/synthesize/agent_tools.py tests/test_agent_tools.py
git commit -m "feat: agent toolbox (list/read/add_reference) with read budget"
```

---

## Task 7: Agent loop + AgenticSynthesizer (happy path)

**Files:**
- Create: `aptitude/synthesize/agent_prompts.py`, `aptitude/synthesize/agentic.py`
- Test: `tests/test_agentic_happy.py`

**Interfaces:**
- Consumes: `Toolbox`/`TOOL_SPECS` (Task 6), `LLMProvider.chat` (Task 1), `Synthesizer`/`synth_registry` (existing), `TemplateSynthesizer._slug`, `SkillDraft`. `FakeProvider` scripted responses drive the ReAct `chat()`.
- Produces: `agent_prompts.system_prompt(user_prompt) -> str` and `agent_prompts.CRITIQUE_NUDGE: str`. `AgenticSynthesizer(budget=6000, max_iterations=12, fallback=True)` registered `"agentic"`; `synthesize(prompt, docs, llm) -> SkillDraft`. Internal `_AgentDidNotConverge(Exception)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentic_happy.py
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.synthesize.agentic import AgenticSynthesizer

def _docs():
    return [Document(Source("a.pdf"), "DocA", [Section("Body", "important facts about widgets")])]

def _action(tool, **args):
    import json
    return f'```action\n{json.dumps({"tool": tool, "arguments": args})}\n```'

def test_agentic_full_session_builds_draft():
    # explore -> read -> add_reference -> finish -> (forced critique) -> finish
    llm = FakeProvider(responses=[
        _action("list_sources"),
        _action("read_source", index=0),
        _action("add_reference", relpath="references/facts.md", content="widget facts"),
        _action("finish", name="Widget Skill", description="Use when building widgets", body="Draft body"),
        _action("finish", name="Widget Skill", description="Use when building widgets", body="Improved body"),
    ])
    draft = AgenticSynthesizer(max_iterations=12).synthesize("make a widget skill", _docs(), llm)
    assert draft.name == "widget-skill"                         # slugified
    assert draft.description == "Use when building widgets"
    assert draft.body == "Improved body"                        # the post-critique finish won
    assert any(f.relpath == "references/facts.md" for f in draft.references)
    assert draft.provenance == ["a.pdf"]

def test_agentic_registered():
    from aptitude.synthesize.base import synth_registry
    assert synth_registry.get("agentic") is AgenticSynthesizer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agentic_happy.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/synthesize/agent_prompts.py
def system_prompt(user_prompt: str) -> str:
    return (
        "You are building a reusable AI skill. Goal:\n"
        f"{user_prompt}\n\n"
        "Work in phases using the available tools: (1) call list_sources, then read_source "
        "to explore the material; (2) optionally add_reference to save distilled notes; "
        "(3) draft the skill; (4) critique your draft against the goal and the sources and "
        "improve it; (5) call finish with the final name, description ('Use when...'), and body. "
        "Call exactly one tool per turn."
    )

CRITIQUE_NUDGE = (
    "Before finalizing: critique this draft against the goal and the sources — is the "
    "description a precise 'Use when...' trigger? Is the body concrete and actionable? "
    "Call finish again with an improved version (or the same if already strong)."
)
```

```python
# aptitude/synthesize/agentic.py
from aptitude.models import SkillDraft
from aptitude.synthesize.base import Synthesizer, synth_registry
from aptitude.synthesize.agent_tools import Toolbox, TOOL_SPECS
from aptitude.synthesize.template_synth import TemplateSynthesizer, _slug
from aptitude.synthesize import agent_prompts

class _AgentDidNotConverge(Exception):
    pass

@synth_registry.register("agentic")
class AgenticSynthesizer(Synthesizer):
    name = "agentic"
    def __init__(self, budget: int = 6000, max_iterations: int = 12, fallback: bool = True):
        self.budget = budget
        self.max_iterations = max_iterations
        self.fallback = fallback

    def synthesize(self, prompt, docs, llm) -> SkillDraft:
        try:
            return self._run_agent(prompt, docs, llm)
        except _AgentDidNotConverge as e:
            if not self.fallback:
                from aptitude.errors import SynthesisError
                raise SynthesisError(f"agentic synthesis did not converge: {e}")
            draft = TemplateSynthesizer(budget=self.budget).synthesize(prompt, docs, llm)
            draft.provenance.append("(agentic did not converge → template fallback)")
            return draft

    def _run_agent(self, prompt, docs, llm) -> SkillDraft:
        tb = Toolbox(docs, read_budget=self.budget)
        messages = [{"role": "system", "content": agent_prompts.system_prompt(prompt)},
                    {"role": "user", "content": "Begin."}]
        critique_done = False
        for _ in range(self.max_iterations):
            turn = llm.chat(messages, TOOL_SPECS)
            messages.append({"role": "assistant", "content": turn.text, "tool_calls": turn.tool_calls})
            if not turn.tool_calls:
                messages.append({"role": "user", "content": "Use a tool, or call finish."})
                continue
            call = turn.tool_calls[0]
            if call.name == "finish":
                if not critique_done:
                    critique_done = True
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "name": "finish", "content": agent_prompts.CRITIQUE_NUDGE})
                    continue
                a = call.arguments
                return SkillDraft(
                    name=_slug(a.get("name", "skill")),
                    description=(a.get("description") or prompt)[:1024],
                    body=a.get("body", ""),
                    references=list(tb.references),
                    provenance=[d.source.raw for d in docs])
            result = tb.dispatch(call.name, call.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result})
        raise _AgentDidNotConverge(f"no finish within {self.max_iterations} iterations")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agentic_happy.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/synthesize/agent_prompts.py aptitude/synthesize/agentic.py tests/test_agentic_happy.py
git commit -m "feat: AgenticSynthesizer agent loop with forced self-critique"
```

---

## Task 8: Convergence fallback, malformed-tool recovery, iteration cap

**Files:**
- Test: `tests/test_agentic_robustness.py`
- Modify (only if a test reveals a gap): `aptitude/synthesize/agentic.py`

**Interfaces:**
- Consumes: `AgenticSynthesizer` (Task 7), `FakeProvider`. Confirms behavior already built in Task 7 (fallback path, dispatch error strings, max-iterations) and locks it with tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentic_robustness.py
import json
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.synthesize.agentic import AgenticSynthesizer
from aptitude.errors import SynthesisError

def _docs():
    return [Document(Source("a.pdf"), "T", [Section("H", "content about things")])]

def _action(tool, **a):
    return f'```action\n{json.dumps({"tool": tool, "arguments": a})}\n```'

def test_never_finishing_falls_back_to_template():
    # agent keeps listing sources, never finishes; then template's 3 calls answer
    loops = [_action("list_sources")] * 12
    template = ["name: fallback-skill\ndescription: Use when X.", "body", "ref"]
    llm = FakeProvider(responses=loops + template)
    draft = AgenticSynthesizer(max_iterations=12).synthesize("p", _docs(), llm)
    assert draft.name == "fallback-skill"
    assert any("template fallback" in p for p in draft.provenance)

def test_no_fallback_raises():
    llm = FakeProvider(responses=[_action("list_sources")] * 3)
    with __import__("pytest").raises(SynthesisError):
        AgenticSynthesizer(max_iterations=3, fallback=False).synthesize("p", _docs(), llm)

def test_malformed_tool_call_is_recoverable():
    # unknown tool -> error observation -> agent recovers and finishes (x2 for critique)
    llm = FakeProvider(responses=[
        _action("bogus_tool"),
        _action("finish", name="ok skill", description="Use when Y.", body="b1"),
        _action("finish", name="ok skill", description="Use when Y.", body="b2"),
    ])
    draft = AgenticSynthesizer(max_iterations=12).synthesize("p", _docs(), llm)
    assert draft.name == "ok-skill" and draft.body == "b2"
```

- [ ] **Step 2: Run test to verify it fails (or passes if Task 7 covered it)**

Run: `pytest tests/test_agentic_robustness.py -v`
Expected: The 3 tests exercise fallback, no-fallback-raises, and malformed recovery. If any fails, fix `agentic.py` minimally (e.g. ensure `dispatch` error strings flow back as observations, ensure the fallback appends provenance). If all pass against Task 7's code, that confirms the behavior — proceed.

- [ ] **Step 3: Implement any fix the tests reveal**

If `test_malformed_tool_call_is_recoverable` fails because an unknown tool raised instead of returning an error observation, confirm `Toolbox.dispatch` returns `"error: unknown tool '<name>'"` (Task 6) and that the loop appends it as a `tool` message (Task 7). No new behavior should be needed; only reconcile if a gap exists.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agentic_robustness.py -v && pytest -q`
Expected: PASS (3 tests); full suite green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_agentic_robustness.py aptitude/synthesize/agentic.py
git commit -m "test: agentic fallback, no-fallback raise, and malformed-tool recovery"
```

---

## Task 9: CLI `--synth`/`--max-iterations`, config, and docs

**Files:**
- Modify: `aptitude/config.py`, `aptitude/cli.py`, `aptitude/pipeline.py` (RunConfig passthrough), `README.md`, `docs/superpowers/specs/2026-08-03-aptitude-skill-generator-design.md`
- Test: `tests/test_cli_synth.py`, `tests/test_config.py` (extend)

**Interfaces:**
- Consumes: `RunConfig` (has `synth`, `budget`), `resolve_config`, `AgenticSynthesizer` (registered via import), `synth_registry`.
- Produces: `create` gains `--synth` (default None → config → `"template"`) and `--max-iterations` (default 12); config resolves `synth` (CLI > `APTITUDE_SYNTH` > `aptitude.toml` > `"template"`); pipeline builds the synthesizer with `max_iterations` when supported. `providers` lists a `tools` marker.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_synth.py
from typer.testing import CliRunner
from aptitude.cli import app
runner = CliRunner()

def test_create_with_agentic_synth(tmp_path):
    pdf = tmp_path / "d.pdf"
    from tests.fixtures.make_pdf import write_sample; write_sample(pdf)
    r = runner.invoke(app, ["create", "-p", "make a skill", "-i", str(pdf),
                            "--provider", "fake", "--synth", "agentic",
                            "--out", str(tmp_path / "out")])
    assert r.exit_code == 0
    assert list((tmp_path / "out").glob("*/SKILL.md"))

def test_create_help_lists_synth():
    assert "--synth" in runner.invoke(app, ["create", "--help"]).output
```

Add to `tests/test_config.py`:

```python
def test_synth_resolves_with_precedence(tmp_path):
    from aptitude.config import resolve_config
    toml = tmp_path / "aptitude.toml"; toml.write_text('synth = "agentic"\n')
    assert resolve_config({}, {}, toml)["synth"] == "agentic"
    assert resolve_config({"synth": "template"}, {}, toml)["synth"] == "template"
    assert resolve_config({}, {}, None)["synth"] == "template"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_synth.py tests/test_config.py -v`
Expected: FAIL — `--synth` unknown / `synth` not in config.

Note on `test_create_with_agentic_synth`: with `--provider fake`, the ReAct `chat()` echoes the rendered prompt (FakeProvider has no queued responses), which contains no valid `action` block → the agent never finishes → **template fallback** produces the SKILL.md. So the test passes via the fallback path (exit 0, SKILL.md written) without scripting a full agent session — this is the intended, robust default behavior.

- [ ] **Step 3: Write minimal implementation**

`aptitude/config.py` — add `synth` to defaults and env:

```python
# in DEFAULTS dict add:  "synth": "template",
# in resolve_config env_cfg add:  "synth": env.get("APTITUDE_SYNTH"),
```

`aptitude/cli.py` — register the agentic synth on import and add options:

```python
# add near other registration imports:
import aptitude.synthesize.template_synth, aptitude.synthesize.agentic  # noqa

# in create(), add options:
           synth: str = typer.Option(None, "--synth"),
           max_iterations: int = typer.Option(12, "--max-iterations"),
# after resolving cfg:
    synth_name = cfg["synth"]
# pass synth + max_iterations into RunConfig:
        rc = RunConfig(prompt=_read_prompt(prompt),
                       sources=[Source(i, type) for i in input],
                       provider=prov_name, model=cfg.get("model"), formats=fmts,
                       out=Path(out), budget=budget, dry_run=dry_run,
                       synth=synth_name, max_iterations=max_iterations)
```

`aptitude/pipeline.py` — carry `max_iterations` and pass it when the synthesizer accepts it:

```python
# add to RunConfig dataclass:  max_iterations: int = 12
# replace the synth construction line:
    synth_cls = synth_registry.get(cfg.synth)
    try:
        synth = synth_cls(budget=cfg.budget, max_iterations=cfg.max_iterations)
    except TypeError:
        synth = synth_cls(budget=cfg.budget)   # template ignores max_iterations
    draft = synth.synthesize(cfg.prompt, docs, provider)
```

`aptitude/cli.py` `providers()` — **leave the existing body unchanged.** The optional per-provider `tools` marker is intentionally omitted: rendering it would require constructing each provider (importing the `anthropic`/`google-genai` SDKs, which aren't installed) or exposing `capabilities` as a class attribute. Not worth it here — note the omission in the report.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_synth.py tests/test_config.py -v && pytest -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Write docs + commit**

Add a **"Synthesizers"** section to `README.md`: `template` (default; fast, fixed 3-call) vs `agentic` (`--synth agentic`; explores sources with tools, self-critiques, falls back to template on non-convergence; `--max-iterations` knob; needs a capable model). Add `synth` to the config precedence list and the example `aptitude.toml`. In `docs/superpowers/specs/2026-08-03-aptitude-skill-generator-design.md` §11, mark the agentic synthesizer **Implemented (V2)**.

```bash
git add aptitude/config.py aptitude/cli.py aptitude/pipeline.py README.md docs/ tests/test_cli_synth.py tests/test_config.py
git commit -m "feat: --synth/--max-iterations, synth config precedence, docs"
```

---

## Self-Review

**Spec coverage:**
- §5 interface extension (`ToolCall`, `AssistantTurn`, `chat()` default) → Task 1. ✓
- §6 ReAct default → Task 1 (`tools_react`). ✓
- §7 native overrides (claude, openai/nvidia, gemini, ollama) → Tasks 2–5; `"tools"` capability in each. ✓
- §8 agent loop + four tools + forced critique + finish assembly → Tasks 6–7. ✓
- §9 convergence/fallback → Task 7 (built) + Task 8 (locked by tests). ✓
- §10 limits (read budget, max_iterations, no fs/network tools) → Task 6 (read budget) + Task 7 (iteration cap) + Task 6 (in-memory only). `chat()` max_tokens: native paths pass a bounded max_tokens (claude explicit; others rely on provider defaults) — acceptable; noted. ✓
- §11 CLI/config → Task 9. ✓
- §12 testing (ReAct, native mocks, integration, contract) → Tasks 1–8; `assert_chat_contract` added Task 1. ✓
- §13 docs → Task 9. ✓

**Placeholder scan:** No "TBD"/"implement later"; every code step has runnable code. Labelled call-outs: the Claude tools shape (confirm via `claude-api`, Task 3), and the `providers` tools-marker intentionally omitted (Task 9) to avoid constructing providers.

**Type consistency:** `ToolCall(id, name, arguments:dict)` and `AssistantTurn(text, tool_calls)` are used identically across Tasks 1–8. `chat(messages, tools) -> AssistantTurn` signature matches in base + all four overrides. Neutral message shapes (`assistant.tool_calls`, `tool.tool_call_id`/`name`/`content`) match across every provider translator and the loop. `AgenticSynthesizer(budget, max_iterations, fallback)` construction matches the pipeline's `synth_cls(budget=..., max_iterations=...)` call (with the `TypeError` fallback for `template`). `Toolbox.dispatch` error strings feed the loop's recovery path.

**One reconciliation note for the implementer (Task 9):** the `providers` command's optional `tools` marker is dropped to avoid instantiating providers (constructing a real Claude/Gemini provider would import the SDK). If a clean class-level capability check is desired later, expose `capabilities` as a class attribute rather than an instance property. Not required for this plan.
