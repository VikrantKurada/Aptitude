from aptitude.llm.fake import FakeProvider
from aptitude.llm.base import provider_registry
from tests.llm_contract import assert_provider_contract

def test_fake_queued_responses_in_order():
    p = FakeProvider(responses=["one", "two"])
    assert p.generate([{"role": "user", "content": "x"}]) == "one"
    assert p.generate([{"role": "user", "content": "x"}]) == "two"

def test_fake_is_registered():
    assert provider_registry.get("fake") is FakeProvider

def test_fake_contract():
    assert_provider_contract(FakeProvider())
