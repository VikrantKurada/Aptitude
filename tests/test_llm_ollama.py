import httpx
import pytest
from aptitude.llm.ollama import OllamaProvider
from aptitude.errors import ProviderError

def test_ollama_parses_chat_response():
    def handler(req):
        return httpx.Response(200, json={"message": {"content": "local reply"}})
    p = OllamaProvider("llama3.1", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.generate([{"role": "user", "content": "hi"}]) == "local reply"

def test_ollama_non_2xx_raises_provider_error():
    def handler(req):
        return httpx.Response(500, json={"error": "x"})
    p = OllamaProvider("m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError):
        p.generate([{"role": "user", "content": "hi"}])

def test_ollama_unreachable_raises_provider_error():
    def handler(req):
        raise httpx.ConnectError("boom", request=req)
    p = OllamaProvider("m", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError):
        p.generate([{"role": "user", "content": "hi"}])
