import httpx
from aptitude.llm.ollama import OllamaProvider

def test_ollama_parses_chat_response():
    def handler(req):
        return httpx.Response(200, json={"message": {"content": "local reply"}})
    p = OllamaProvider("llama3.1", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.generate([{"role": "user", "content": "hi"}]) == "local reply"
