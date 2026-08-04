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
