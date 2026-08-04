import pytest
from aptitude.llm.claude import ClaudeProvider, _build_claude_kwargs
from aptitude.llm.gemini import GeminiProvider
from aptitude.errors import ProviderError

class _FakeClient:
    def generate(self, model, messages, **opts): return "sdk reply"

class _RaisingClient:
    def generate(self, model, messages, **opts): raise RuntimeError("boom")

def test_claude_uses_injected_client():
    assert ClaudeProvider("m", "key", client=_FakeClient()).generate(
        [{"role": "user", "content": "x"}]) == "sdk reply"

def test_gemini_uses_injected_client():
    assert GeminiProvider("m", "key", client=_FakeClient()).generate(
        [{"role": "user", "content": "x"}]) == "sdk reply"

def test_build_claude_kwargs_omits_system_when_absent():
    kwargs = _build_claude_kwargs("m", [{"role": "user", "content": "hi"}])
    assert "system" not in kwargs
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]

def test_build_claude_kwargs_includes_system_when_present():
    messages = [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
    ]
    kwargs = _build_claude_kwargs("m", messages)
    assert kwargs["system"] == "be terse"
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]

def test_claude_build_without_api_key_raises_provider_error():
    with pytest.raises(ProviderError):
        ClaudeProvider.build({}, {})

def test_gemini_build_without_api_key_raises_provider_error():
    with pytest.raises(ProviderError):
        GeminiProvider.build({}, {})

def test_claude_generate_wraps_client_error():
    with pytest.raises(ProviderError):
        ClaudeProvider("m", "key", client=_RaisingClient()).generate(
            [{"role": "user", "content": "x"}])

def test_gemini_generate_wraps_client_error():
    with pytest.raises(ProviderError):
        GeminiProvider("m", "key", client=_RaisingClient()).generate(
            [{"role": "user", "content": "x"}])
