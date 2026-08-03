class Registry:
    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, type] = {}

    def register(self, name: str):
        def deco(cls):
            if name in self._items:
                raise ValueError(f"{self.kind} '{name}' already registered")
            self._items[name] = cls
            return cls
        return deco

    def get(self, name: str) -> type:
        if name not in self._items:
            raise KeyError(f"unknown {self.kind} '{name}'; available: {self.names()}")
        return self._items[name]

    def names(self) -> list[str]:
        return list(self._items)
