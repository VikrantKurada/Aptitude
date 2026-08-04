import httpx, pytest
from aptitude.llm.openai import OpenAICompatibleProvider
from aptitude.llm.base import provider_registry
from aptitude.errors import ProviderError
from tests.llm_contract import assert_provider_contract

def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_generate_parses_openai_response():
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi there"}}]})
    p = OpenAICompatibleProvider("m", "key", "https://x/v1", client=_client(handler))
    assert p.generate([{"role": "user", "content": "yo"}]) == "hi there"
    assert_provider_contract(p)

def test_non_2xx_raises_provider_error():
    p = OpenAICompatibleProvider("m", "key", "https://x/v1",
        client=_client(lambda req: httpx.Response(401, json={"error": "bad key"})))
    with pytest.raises(ProviderError):
        p.generate([{"role": "user", "content": "yo"}])

def test_openai_and_nvidia_registered():
    assert provider_registry.get("openai") and provider_registry.get("nvidia")
