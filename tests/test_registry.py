import pytest
from aptitude.registry import Registry

def test_register_and_get():
    r = Registry("thing")
    @r.register("a")
    class A: ...
    assert r.get("a") is A
    assert r.names() == ["a"]

def test_duplicate_name_raises():
    r = Registry("thing")
    @r.register("a")
    class A: ...
    with pytest.raises(ValueError):
        @r.register("a")
        class B: ...

def test_unknown_name_lists_available():
    r = Registry("thing")
    @r.register("a")
    class A: ...
    with pytest.raises(KeyError, match="a"):
        r.get("nope")
