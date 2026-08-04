import pytest
from aptitude.llm.factory import build_provider
from aptitude.llm.fake import FakeProvider
from aptitude.errors import ProviderError

def test_build_provider_fake_returns_fakeprovider():
    assert isinstance(build_provider("fake", {}, {}), FakeProvider)

def test_build_provider_unknown_raises_provider_error():
    with pytest.raises(ProviderError):
        build_provider("no-such-provider-xyz", {}, {})
