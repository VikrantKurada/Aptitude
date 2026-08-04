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
