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
    try:
        data = json.loads(m.group(1))
        name = data["tool"]
        args = data.get("arguments", {})
        if not isinstance(args, dict):
            return text, []          # malformed -> full text, no calls
    except (ValueError, KeyError, TypeError):
        return text, []              # malformed -> full text, no calls
    prose = text[: m.start()]
    return prose, [ToolCall(id="react-0", name=name, arguments=args)]
