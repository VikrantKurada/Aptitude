# Adding a Provider, Format, or Adapter

Aptitude has four extension points, all built the same way: an abstract base class with one abstract method, a module-level `Registry`, a `@registry.register("name")` decorator on the concrete class, and an import that makes the module load at startup.

| Seam | ABC | Registry | Registered by importing in |
|------|-----|----------|----------------------------|
| Provider | `LLMProvider` (`aptitude/llm/base.py:18`) | `provider_registry` (`llm/base.py:5`) | `aptitude/llm/__init__.py` |
| Ingestion adapter | `IngestionAdapter` (`aptitude/ingest/base.py:10`) | `ingest_registry` (`ingest/base.py:8`) | `aptitude/cli.py:12-13` |
| Synthesizer | `Synthesizer` (`aptitude/synthesize/base.py:7`) | `synth_registry` (`synthesize/base.py:5`) | `aptitude/cli.py:14` |
| Exporter | `Exporter` (`aptitude/export/base.py:8`) | `export_registry` (`export/base.py:6`) | `aptitude/cli.py:10-11` |

`Registry.register` raises `ValueError` if the name is already taken (`aptitude/registry.py:9`), so name collisions fail at import rather than silently overwriting. `Registry.get` raises `KeyError` listing the available names on a miss (`registry.py:16`).

For why the seams are shaped this way, see [The Architect's View](architecture.md).

---

## A new provider

### 1. Subclass `LLMProvider`

```python
# aptitude/llm/myprovider.py
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

@provider_registry.register("myprovider")
class MyProvider(LLMProvider):
    name = "myprovider"

    def __init__(self, model, api_key, client=None):
        self.model = model
        self.context_window = 32000
        self._client = client or _MyClient(api_key)

    def generate(self, messages: list[dict], **opts) -> str:
        try:
            return self._client.complete(self.model, messages, **opts)
        except Exception as e:
            raise ProviderError(f"MyProvider call failed: {e}") from e

    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("myprovider", env)
        if not key:
            raise ProviderError("MYPROVIDER_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["myprovider"], key)
```

What is required and what is not:

- **`generate(messages, **opts) -> str`** is the only abstract method (`llm/base.py:23-24`). `messages` is a list of `{"role": ..., "content": ...}` dicts; the return value is the assistant's text.
- **`context_window`** is a class or instance attribute; the base default is `8000` (`llm/base.py:21`). Declare the real number for your model. Note that nothing in the pipeline currently reads it — see [limitations.md](../limitations.md).
- **`build(cfg, env)`** is a classmethod, not part of the ABC. `build_provider` calls it if present and raises `ProviderError` otherwise (`aptitude/llm/factory.py:12-14`), so without it the provider is registered but not constructible from the CLI.
- **`count_tokens`** defaults to `max(1, len(text) // 4)` (`llm/base.py:26-27`). Override it if you have a real tokenizer.
- **`capabilities`** defaults to `{"chat"}` (`llm/base.py:29-31`). Providers with native tool support return `{"chat", "tools"}`. Nothing in `aptitude/` branches on this yet.
- **Accept an injectable client** (`client=None` above). Every existing provider does, which is what lets its tests run offline against an `httpx.MockTransport` or a stub object.

### 2. Decide whether to override `chat()`

`LLMProvider.chat()` already works (`llm/base.py:33-38`). The default renders the tool catalog and the transcript into a single text prompt, calls your `generate()`, and parses a fenced `action` block of JSON back out (`aptitude/llm/tools_react.py`). **If you skip `chat()`, your provider still runs the full `--synth agentic` loop.**

Override it when the API has native tool calling, which is faster and more reliable:

```python
    def chat(self, messages, tools) -> AssistantTurn:
        resp = self._client.chat(self.model, messages, tools)
        return AssistantTurn(text=resp.text, tool_calls=[
            ToolCall(id=c.id, name=c.name, arguments=c.args) for c in resp.calls])
```

The translation layer between Aptitude's message dicts and each vendor's wire format lives next to each provider: `_to_anthropic` (`llm/claude.py:13-29`), `_to_gemini_contents` (`llm/gemini.py:5-21`), `_to_openai_messages` (`llm/openai.py:11-23`), `_to_ollama_messages` (`llm/ollama.py:6-17`). Copy the closest one.

### 3. OpenAI-compatible endpoints are eight lines

If the endpoint speaks the OpenAI chat-completions API, subclass `OpenAICompatibleProvider` instead and supply only a default model and a base URL. That is the whole of the `nvidia` provider (`llm/openai.py:67-74`):

```python
@provider_registry.register("nvidia")
class NvidiaProvider(OpenAICompatibleProvider):
    name = "nvidia"
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["nvidia"],
                   api_key_for("nvidia", env),
                   cfg.get("base_url") or "https://integrate.api.nvidia.com/v1")
```

`generate()`, `chat()` with native tools, and `capabilities` all come from the parent. This covers LM Studio, vLLM, Together, Groq, and anything else with an OpenAI-shaped `/v1/chat/completions`.

### 4. Wire up config and registration

- Add a default model to `DEFAULT_MODELS` (`aptitude/config.py:4-6`).
- Add the API key environment variable to `_KEY_ENV` (`config.py:7-8`) so `aptitude providers` reports `ready` or `no key` correctly (`cli.py:76-78`).
- Add the import to `aptitude/llm/__init__.py` so the decorator runs.

### 5. Pass the contract test

`tests/llm_contract.py` is the shared assertion set:

```python
from tests.llm_contract import assert_provider_contract, assert_chat_contract

def test_myprovider_contract():
    p = MyProvider("m", "key", client=_stub())
    assert_provider_contract(p)   # generate() returns a non-empty str;
                                  # count_tokens("abcd") >= 1; context_window > 0
    assert_chat_contract(p)       # chat() returns an AssistantTurn with a str .text
```

Also assert your provider is registered (`assert provider_registry.get("myprovider")`) and that a non-2xx response raises `ProviderError` — see `tests/test_llm_openai.py` for the pattern using `httpx.MockTransport`.

---

## A new exporter

### 1. Implement `export`

```python
# aptitude/export/myformat.py
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.models import SkillDraft

@export_registry.register("my-format")
class MyFormatExporter(Exporter):
    name = "my-format"
    def export(self, draft: SkillDraft, out_dir: Path) -> list[Path]:
        root = Path(out_dir) / draft.name
        root.mkdir(parents=True, exist_ok=True)
        p = root / "skill.myfmt"
        p.write_text(render(draft), encoding="utf-8")
        return [p]
```

Rules the existing exporters all follow:

- **Return every path you wrote.** The CLI counts them and `-v` prints them (`cli.py:64-67`).
- **Write into `out_dir / draft.name`.** All formats share that one flat directory; `zip` archives whatever is in it (`export/packager.py`).
- **Always `encoding="utf-8"`** — Windows defaults to the ANSI code page otherwise.
- **Read `draft.references` and `draft.scripts` if the format carries attachments** (`export/claude_skill.py:23`). `draft.scripts` and `draft.tools` are always empty today; see [limitations.md](../limitations.md).
- **Returning `[]` is legal** for a format that has nothing to emit for a given draft (`export/mcp_manifest.py:9`), but `assert_exporter_contract` requires at least one path, so test that case separately.

### 2. Register the import

Add the module to the import line in `aptitude/cli.py:10-11`. Once it is there, `aptitude formats` lists it and `--format all` includes it, both of which read `export_registry.names()` (`cli.py:43`, `cli.py:80-83`).

### 3. Pass the contract test

```python
from tests.export_contract import assert_exporter_contract

def test_myformat_contract(tmp_path):
    draft = SkillDraft(name="s", description="d", body="b")
    paths = assert_exporter_contract(MyFormatExporter(), draft, tmp_path)
    # returns non-empty and every path exists; assert content specifics here
    assert paths[0].read_text(encoding="utf-8").startswith("...")
```

Note that `tests/test_docs.py` parametrizes over `export_registry.names()` and fails unless the new format name appears somewhere in `README.md` or `docs/` — document it in [features.md](../product/features.md) as part of the same change.

---

## A new ingestion adapter

### 1. Implement `ingest`

```python
# aptitude/ingest/mykind.py
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

@ingest_registry.register("mykind")
class MyKindAdapter(IngestionAdapter):
    name = "mykind"
    def __init__(self, fetch=None):
        self._fetch = fetch or _default_fetch      # inject I/O for offline tests

    def ingest(self, src: Source) -> Document:
        try:
            raw = self._fetch(src.raw)
        except Exception as e:
            raise IngestionError(f"cannot read {src.raw}: {e}") from e
        sections = [Section(heading, text) for heading, text in parse(raw)]
        if not sections:
            raise IngestionError(f"no readable content in {src.raw}")
        return Document(src, title, sections, {"units": len(sections)})
```

- **`ingest(src) -> Document`** is the only abstract method (`ingest/base.py:12-13`).
- **Raise `IngestionError` on any failure.** `pipeline.run()` catches per-source exceptions, records them in `RunResult.skipped`, and continues with the remaining inputs (`pipeline.py:36-40`), so a broken source degrades the run instead of ending it.
- **Take the I/O as a constructor argument.** `WebAdapter` takes `fetch` (`ingest/web.py:17-18`) and `GithubAdapter` takes `clone` (`ingest/github.py:32-33`), which is how their tests run with no network.
- **Sections are the unit of chunking.** `chunk_document` splits and repacks section bodies (`aptitude/process/chunker.py`), and `Toolbox.list_sources` shows their headings to the agent (`synthesize/agent_tools.py:28-33`). Give them meaningful headings — page numbers, chapter names, file paths.

### 2. Extend `detect_kind()`

`--type auto` routes each input through `detect_kind` (`ingest/base.py:15-32`), which checks file extension first, then URL host, then the bare `owner/repo` shorthand, and raises `IngestionError` if nothing matches. Add your branch in the right priority slot, and add the new value to the `Kind` literal in `aptitude/models.py:5`.

```python
    if low.endswith(".myext"):
        return "mykind"
```

Users can bypass detection with `--type mykind`, but that forces the type for **every** `-i` input in the run.

### 3. Add a fixture and a test

Fixtures live in `tests/fixtures/` and build their input on the fly rather than committing binaries — `make_pdf.py` writes a one-page PDF with `pypdf`, `make_epub.py` builds an EPUB with `ebooklib`. Follow that pattern:

```python
def test_mykind_produces_document(tmp_path):
    p = tmp_path / "doc.myext"; write_sample(p)
    doc = MyKindAdapter().ingest(Source(str(p), "mykind"))
    assert doc.sections and doc.title == "doc"
```

Add the detection case to the parametrized list in `tests/test_ingest_base.py`, and the import to `aptitude/cli.py:12-13`.

---

## House rules

- **Tests are offline.** No test in the suite makes a network call. Providers take an injectable client, adapters take an injectable fetch or clone, and `FakeProvider` (`aptitude/llm/fake.py`) returns scripted strings — including the fenced action blocks that drive the whole agentic loop (`tests/test_agentic_happy.py`).
- **Tests are deterministic.** Nothing in a test depends on model output. Note that this is a property of the tests, not of Aptitude: `template` makes the same three provider calls every run, but nothing in `aptitude/` pins a temperature or a seed, so real output varies between runs.
- **Live tests are opt-in.** A test that hits a real provider API must be marked `@pytest.mark.live`. The marker is declared in `pyproject.toml` and `addopts = "-m 'not live'"` deselects it by default, so `pytest` stays offline. No test carries the marker today, so `pytest -m live` currently collects nothing — it is the command for running such tests deliberately once some exist.
- **Run the whole suite before you commit.** 33 `test_*.py` modules (`tests/` also holds `__init__.py` and the two shared contract helpers, which pytest doesn't collect), and CI runs them on Python 3.11, 3.12, 3.13, and 3.14.

```bash
pip install -e ".[dev]"
python -m pytest -q          # offline, live tests deselected
python -m pytest -m live     # collects nothing today; for live tests once they exist
```

[← Back to the documentation index](../index.md)
