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

def test_fake_echo_exhausted_queue_has_fake_prefix():
    p = FakeProvider(responses=[])
    assert p.generate([{"role": "user", "content": "hello"}]) == "[fake] hello"

def test_fake_echo_truncates_at_200_chars():
    long = "x" * 250
    p = FakeProvider()
    assert p.generate([{"role": "user", "content": long}]) == "[fake] " + long[:200]

def test_fake_echo_disabled_returns_bare_marker():
    p = FakeProvider(echo=False)
    assert p.generate([{"role": "user", "content": "hello"}]) == "[fake]"

def test_fake_echo_uses_last_user_message_in_multi_turn():
    p = FakeProvider()
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]
    assert p.generate(messages) == "[fake] second"
