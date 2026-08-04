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
