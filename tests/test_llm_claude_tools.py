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
