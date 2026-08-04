from aptitude.llm.claude import ClaudeProvider
from aptitude.llm.gemini import GeminiProvider

class _FakeClient:
    def generate(self, model, messages, **opts): return "sdk reply"

def test_claude_uses_injected_client():
    assert ClaudeProvider("m", "key", client=_FakeClient()).generate(
        [{"role": "user", "content": "x"}]) == "sdk reply"

def test_gemini_uses_injected_client():
    assert GeminiProvider("m", "key", client=_FakeClient()).generate(
        [{"role": "user", "content": "x"}]) == "sdk reply"
