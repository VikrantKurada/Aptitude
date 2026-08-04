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

def test_parse_action_invalid_json_returns_full_text():
    inp = "Hmm.\n```action\n{not: valid json}\n```\ntrailing"
    prose, calls = tools_react.parse_action(inp)
    assert calls == [] and prose == inp          # full text preserved, nothing dropped

def test_fake_provider_chat_returns_assistant_turn():
    p = FakeProvider(responses=['```action\n{"tool":"read_source","arguments":{"index":1}}\n```'])
    turn = p.chat([{"role": "user", "content": "go"}], TOOLS)
    assert isinstance(turn, AssistantTurn)
    assert turn.tool_calls[0].name == "read_source" and turn.tool_calls[0].arguments == {"index": 1}

def test_fake_provider_chat_no_tools_is_plain_text():
    p = FakeProvider(responses=["final answer"])
    turn = p.chat([{"role": "user", "content": "hi"}], [])
    assert turn.text == "final answer" and turn.tool_calls == []

def test_render_prompt_renders_tools_and_transcript():
    from aptitude.llm.base import ToolCall
    msgs = [{"role": "user", "content": "U"},
            {"role": "assistant", "content": "drafting",
             "tool_calls": [ToolCall("react-0", "read_source", {"index": 0})]},
            {"role": "tool", "tool_call_id": "react-0", "name": "read_source", "content": "the text"}]
    out = tools_react.render_prompt(msgs, TOOLS)
    assert "read_source" in out                    # tool catalog + rendered action
    assert "action" in out.lower()                 # action-syntax guide
    assert "OBSERVATION" in out and "the text" in out   # tool result rendered, no crash
