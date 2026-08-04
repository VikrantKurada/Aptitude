from aptitude.llm.base import provider_registry
from aptitude.llm.fake import FakeProvider
from aptitude.errors import ProviderError

def build_provider(name, cfg, env):
    if name == "fake":
        return FakeProvider()
    try:
        cls = provider_registry.get(name)
    except KeyError as e:
        raise ProviderError(f"unknown provider '{name}'") from e
    if hasattr(cls, "build"):
        return cls.build(cfg, env)
    raise ProviderError(f"provider '{name}' cannot be constructed")
