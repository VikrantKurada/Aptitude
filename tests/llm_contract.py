def assert_provider_contract(provider):
    out = provider.generate([{"role": "user", "content": "hello"}])
    assert isinstance(out, str) and out
    assert provider.count_tokens("abcd") >= 1
    assert provider.context_window > 0
