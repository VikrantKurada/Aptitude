# Aptitude Skill Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that turns a prompt + artifacts (PDF, EPUB, web page, GitHub repo) into a reusable skill, emitted in multiple formats using a pluggable LLM provider.

**Architecture:** A linear `Ingest → Process → Synthesize → Export` pipeline. Every stage boundary is an ABC selected from a string-keyed registry, so providers, adapters, and exporters are drop-in. A format-neutral `SkillDraft` is the pivot between synthesis and export. A deterministic `FakeProvider` lets the entire pipeline be tested without network access.

**Tech Stack:** Python 3.11+, Typer (CLI), pypdf (PDF), ebooklib + beautifulsoup4 (EPUB/web), httpx (web fetch + OpenAI-compatible/Ollama providers), lazy-imported `anthropic` / `google-genai` SDKs (Claude/Gemini), `tomllib` (stdlib) + `tomli-w` (config), pytest.

## Global Constraints

- Python `>=3.11` (relies on stdlib `tomllib`).
- API keys are read **only** from environment variables, never written to config files.
- Provider SDK imports (`anthropic`, `google-genai`) are **lazy** (imported inside methods), so core install has no hard dependency on them.
- Skill `name`: kebab-case, `^[a-z0-9]+(-[a-z0-9]+)*$`, max 64 chars.
- Skill `description`: non-empty, max 1024 chars.
- All code is TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.
- Exit codes: `0` success, `1` partial (some inputs skipped), `2` fatal.
- Tests never hit the network by default; live-provider tests sit behind a `@pytest.mark.live` marker that is deselected in the default run.

---

## File Structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, pytest config |
| `aptitude/models.py` | Core dataclasses (`Source`, `Section`, `Document`, `Chunk`, `SkillFile`, `ToolSpec`, `SkillDraft`) |
| `aptitude/errors.py` | Exception hierarchy |
| `aptitude/registry.py` | Generic string-keyed `Registry` |
| `aptitude/config.py` | Layered config resolution |
| `aptitude/llm/base.py` | `LLMProvider` ABC + provider registry |
| `aptitude/llm/fake.py` | `FakeProvider` (deterministic, test/offline) |
| `aptitude/llm/openai.py` | `OpenAICompatibleProvider` base + `openai` + `nvidia` |
| `aptitude/llm/ollama.py` | `OllamaProvider` |
| `aptitude/llm/claude.py` | `ClaudeProvider` |
| `aptitude/llm/gemini.py` | `GeminiProvider` |
| `aptitude/process/tokens.py` | Token counting |
| `aptitude/process/chunker.py` | Token-aware chunking |
| `aptitude/process/summarizer.py` | Map-reduce summarization |
| `aptitude/ingest/base.py` | `IngestionAdapter` ABC + registry + `detect_kind` |
| `aptitude/ingest/{pdf,epub,web,github}.py` | One adapter each |
| `aptitude/synthesize/base.py` | `Synthesizer` ABC |
| `aptitude/synthesize/prompts.py` | Meta-prompts |
| `aptitude/synthesize/template_synth.py` | v1 synthesizer |
| `aptitude/export/base.py` | `Exporter` ABC + registry |
| `aptitude/export/{claude_skill,generic_prompt,local_llm,mcp_manifest,packager}.py` | One exporter each |
| `aptitude/validate/validator.py` | Skill validation |
| `aptitude/pipeline.py` | Orchestration |
| `aptitude/cli.py` | Typer CLI |

---

## Task 1: Project scaffold + core models + errors

**Files:**
- Create: `pyproject.toml`, `aptitude/__init__.py`, `aptitude/models.py`, `aptitude/errors.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: dataclasses `Source(raw:str, kind:str="auto")`, `Section(heading:str, text:str, code:str|None=None)`, `Document(source:Source, title:str, sections:list[Section], metadata:dict=field(default_factory=dict))`, `Chunk(text:str, token_count:int, provenance:str)`, `SkillFile(relpath:str, content:str)`, `ToolSpec(name:str, description:str, parameters:dict=field(default_factory=dict))`, `SkillDraft(name:str, description:str, body:str, references:list[SkillFile]=…, scripts:list[SkillFile]=…, tools:list[ToolSpec]=…, provenance:list[str]=…)`. Exceptions: `AptitudeError` and subclasses `ConfigError, IngestionError, ProviderError, SynthesisError, ExportError, ValidationError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from aptitude.models import Source, Document, Section, SkillDraft
from aptitude.errors import AptitudeError, IngestionError

def test_document_defaults_metadata():
    doc = Document(source=Source("a.pdf"), title="A", sections=[Section("H", "body")])
    assert doc.metadata == {}
    assert doc.sections[0].code is None

def test_skilldraft_default_collections_are_independent():
    a = SkillDraft(name="x", description="d", body="b")
    b = SkillDraft(name="y", description="d", body="b")
    a.references.append(object())
    assert b.references == []  # no shared mutable default

def test_source_default_kind_is_auto():
    assert Source("x").kind == "auto"

def test_error_hierarchy():
    assert issubclass(IngestionError, AptitudeError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: aptitude`.

- [ ] **Step 3: Write pyproject + package + implementation**

```toml
# pyproject.toml
[project]
name = "aptitude"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["typer>=0.12", "httpx>=0.27", "pypdf>=4.2",
                "ebooklib>=0.18", "beautifulsoup4>=4.12", "tomli-w>=1.0"]

[project.optional-dependencies]
claude = ["anthropic>=0.34"]
gemini = ["google-genai>=0.3"]
dev = ["pytest>=8.0"]

[project.scripts]
aptitude = "aptitude.cli:app"

[tool.pytest.ini_options]
markers = ["live: hits real provider APIs (deselected by default)"]
addopts = "-m 'not live'"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

```python
# aptitude/errors.py
class AptitudeError(Exception): ...
class ConfigError(AptitudeError): ...
class IngestionError(AptitudeError): ...
class ProviderError(AptitudeError): ...
class SynthesisError(AptitudeError): ...
class ExportError(AptitudeError): ...
class ValidationError(AptitudeError): ...
```

```python
# aptitude/models.py
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["pdf", "epub", "web", "github", "auto"]

@dataclass
class Source:
    raw: str
    kind: Kind = "auto"

@dataclass
class Section:
    heading: str
    text: str
    code: str | None = None

@dataclass
class Document:
    source: Source
    title: str
    sections: list[Section]
    metadata: dict = field(default_factory=dict)

@dataclass
class Chunk:
    text: str
    token_count: int
    provenance: str

@dataclass
class SkillFile:
    relpath: str
    content: str

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)

@dataclass
class SkillDraft:
    name: str
    description: str
    body: str
    references: list[SkillFile] = field(default_factory=list)
    scripts: list[SkillFile] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
```

Create empty `aptitude/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pip install -e ".[dev]" && pytest tests/test_models.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml aptitude/ tests/test_models.py
git commit -m "feat: project scaffold, core models, error hierarchy"
```

---

## Task 2: Component registry

**Files:**
- Create: `aptitude/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces: `Registry(kind:str)` with `.register(name:str)` (decorator returning the class), `.get(name:str) -> type` (raises `KeyError` with available names), `.names() -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/registry.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registry.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/registry.py tests/test_registry.py
git commit -m "feat: generic component registry"
```

---

## Task 3: Config loader

**Files:**
- Create: `aptitude/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `DEFAULT_MODELS: dict[str,str]`; `resolve_config(cli:dict, env:dict, toml_path:Path|None) -> dict` merging with precedence CLI > env > toml > defaults; `api_key_for(provider:str, env:dict) -> str|None` (reads `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`NVIDIA_API_KEY`/`OPENAI_API_KEY`); `default_provider(env:dict) -> str` (`claude` if its key set, else `ollama`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from aptitude.config import resolve_config, default_provider, api_key_for

def test_cli_overrides_env_and_toml(tmp_path):
    toml = tmp_path / "aptitude.toml"
    toml.write_text('provider = "gemini"\nmodel = "g-toml"\n')
    cfg = resolve_config(cli={"model": "cli-model"},
                         env={"APTITUDE_PROVIDER": "nvidia"},
                         toml_path=toml)
    assert cfg["model"] == "cli-model"        # CLI wins
    assert cfg["provider"] == "nvidia"        # env beats toml

def test_default_provider_prefers_claude_key():
    assert default_provider({"ANTHROPIC_API_KEY": "x"}) == "claude"
    assert default_provider({}) == "ollama"

def test_api_key_lookup():
    assert api_key_for("nvidia", {"NVIDIA_API_KEY": "k"}) == "k"
    assert api_key_for("ollama", {}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/config.py
import tomllib
from pathlib import Path

DEFAULT_MODELS = {"claude": "claude-sonnet-5", "gemini": "gemini-2.0-flash",
                  "nvidia": "meta/llama-3.1-70b-instruct",
                  "openai": "gpt-4o-mini", "ollama": "llama3.1"}
_KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY",
            "nvidia": "NVIDIA_API_KEY", "openai": "OPENAI_API_KEY"}
DEFAULTS = {"provider": None, "model": None, "format": "claude-skill",
            "out": "./out", "max_tokens_budget": None, "cache": ".aptitude-cache"}

def api_key_for(provider: str, env: dict) -> str | None:
    return env.get(_KEY_ENV.get(provider, ""), None) or None

def default_provider(env: dict) -> str:
    return "claude" if env.get("ANTHROPIC_API_KEY") else "ollama"

def resolve_config(cli: dict, env: dict, toml_path: Path | None) -> dict:
    cfg = dict(DEFAULTS)
    if toml_path and Path(toml_path).exists():
        cfg.update({k: v for k, v in tomllib.loads(Path(toml_path).read_text()).items()})
    env_cfg = {"provider": env.get("APTITUDE_PROVIDER"), "model": env.get("APTITUDE_MODEL")}
    cfg.update({k: v for k, v in env_cfg.items() if v is not None})
    cfg.update({k: v for k, v in cli.items() if v is not None})
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 tests). NOTE: model IDs in `DEFAULT_MODELS["claude"]` are placeholders to be confirmed against the `claude-api` skill in Task 12/18.

- [ ] **Step 5: Commit**

```bash
git add aptitude/config.py tests/test_config.py
git commit -m "feat: layered config resolution"
```

---

## Task 4: LLM provider base + FakeProvider + contract

**Files:**
- Create: `aptitude/llm/__init__.py`, `aptitude/llm/base.py`, `aptitude/llm/fake.py`
- Test: `tests/llm_contract.py`, `tests/test_llm_fake.py`

**Interfaces:**
- Produces: ABC `LLMProvider` with attrs `name:str`, `model:str`, `context_window:int`, methods `generate(messages:list[dict], **opts) -> str`, `count_tokens(text:str) -> int`, property `capabilities:set[str]`. `provider_registry = Registry("provider")`. `FakeProvider(model="fake", context_window=8000, responses:list[str]|None=None, echo:bool=True)` registered as `"fake"`; deterministic: returns queued `responses` in order, else echoes a summary of the last user message. `count_tokens` = `max(1, len(text)//4)`. Shared `assert_provider_contract(provider)` in `tests/llm_contract.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/llm_contract.py
def assert_provider_contract(provider):
    out = provider.generate([{"role": "user", "content": "hello"}])
    assert isinstance(out, str) and out
    assert provider.count_tokens("abcd") >= 1
    assert provider.context_window > 0

# tests/test_llm_fake.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_fake.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/llm/base.py
from abc import ABC, abstractmethod
from aptitude.registry import Registry

provider_registry = Registry("provider")

class LLMProvider(ABC):
    name: str = "base"
    model: str = ""
    context_window: int = 8000

    @abstractmethod
    def generate(self, messages: list[dict], **opts) -> str: ...

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    @property
    def capabilities(self) -> set[str]:
        return {"chat"}
```

```python
# aptitude/llm/fake.py
from aptitude.llm.base import LLMProvider, provider_registry

@provider_registry.register("fake")
class FakeProvider(LLMProvider):
    name = "fake"
    def __init__(self, model="fake", context_window=8000, responses=None, echo=True):
        self.model, self.context_window = model, context_window
        self._responses = list(responses or [])
        self._echo = echo
    def generate(self, messages, **opts) -> str:
        if self._responses:
            return self._responses.pop(0)
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"[fake] {last[:200]}" if self._echo else "[fake]"
```

```python
# aptitude/llm/__init__.py
from aptitude.llm import fake  # noqa: F401  (registers FakeProvider)
```

Create empty `tests/__init__.py` so `tests.llm_contract` is importable.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_fake.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/ tests/llm_contract.py tests/test_llm_fake.py tests/__init__.py
git commit -m "feat: LLMProvider ABC, registry, FakeProvider, provider contract"
```

---

## Task 5: Token counting + chunker

**Files:**
- Create: `aptitude/process/__init__.py`, `aptitude/process/tokens.py`, `aptitude/process/chunker.py`
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: `Document`, `Chunk`, `Section` (Task 1); `LLMProvider.count_tokens` (Task 4).
- Produces: `estimate_tokens(text:str) -> int` (`max(1, len(text)//4)`); `chunk_document(doc:Document, max_tokens:int, count=estimate_tokens) -> list[Chunk]` — packs sections into chunks under `max_tokens`, splitting oversized sections on paragraph boundaries; each `Chunk.provenance` = `"<doc.title> › <heading>"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chunker.py
from aptitude.models import Document, Source, Section
from aptitude.process.chunker import chunk_document

def _doc(*sections):
    return Document(Source("x"), "DocT", [Section(h, t) for h, t in sections])

def test_small_doc_one_chunk():
    chunks = chunk_document(_doc(("H1", "short text")), max_tokens=1000)
    assert len(chunks) == 1
    assert "DocT" in chunks[0].provenance and "H1" in chunks[0].provenance

def test_oversized_section_is_split():
    big = "para. " * 500  # ~3000 chars ≈ 750 tokens
    chunks = chunk_document(_doc(("Big", big)), max_tokens=100)
    assert len(chunks) > 1
    assert all(c.token_count <= 100 for c in chunks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/process/tokens.py
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

```python
# aptitude/process/chunker.py
from aptitude.models import Document, Chunk
from aptitude.process.tokens import estimate_tokens

def _split_text(text, max_tokens, count):
    parts, buf = [], ""
    for para in text.split("\n\n") if "\n\n" in text else text.split(". "):
        candidate = (buf + "\n\n" + para).strip()
        if buf and count(candidate) > max_tokens:
            parts.append(buf.strip()); buf = para
        else:
            buf = candidate
    if buf.strip():
        parts.append(buf.strip())
    # hard-split any still-too-large part by characters
    out = []
    for p in parts:
        while count(p) > max_tokens:
            cut = max_tokens * 4
            out.append(p[:cut]); p = p[cut:]
        if p:
            out.append(p)
    return out

def chunk_document(doc: Document, max_tokens: int, count=estimate_tokens) -> list[Chunk]:
    chunks: list[Chunk] = []
    for sec in doc.sections:
        prov = f"{doc.title} › {sec.heading}"
        body = sec.text if not sec.code else f"{sec.text}\n\n```\n{sec.code}\n```"
        for piece in _split_text(body, max_tokens, count):
            chunks.append(Chunk(piece, count(piece), prov))
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chunker.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/process/ tests/test_chunker.py
git commit -m "feat: token estimation and document chunker"
```

---

## Task 6: Map-reduce summarizer

**Files:**
- Create: `aptitude/process/summarizer.py`
- Test: `tests/test_summarizer.py`

**Interfaces:**
- Consumes: `Document` (Task 1), `chunk_document` (Task 5), `LLMProvider` (Task 4).
- Produces: `distill(docs:list[Document], llm:LLMProvider, budget:int) -> str` — if total tokens ≤ budget, returns concatenated text with provenance headers unchanged; else map-reduce: summarize each chunk via `llm.generate`, concatenate summaries, and if still over budget, reduce again. Each summary keeps a `provenance` header line.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_summarizer.py
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.process.summarizer import distill

def _doc(text): return Document(Source("x"), "T", [Section("H", text)])

def test_under_budget_passthrough_no_llm_calls():
    doc = _doc("small body")
    out = distill([doc], FakeProvider(responses=[]), budget=10000)
    assert "small body" in out

def test_over_budget_triggers_summarization():
    doc = _doc("word " * 4000)  # ~5000 tokens
    llm = FakeProvider(responses=["SUMMARY"] * 50)
    out = distill([doc], llm, budget=200)
    assert "SUMMARY" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/process/summarizer.py
from aptitude.models import Document
from aptitude.process.tokens import estimate_tokens
from aptitude.process.chunker import chunk_document

def _corpus(docs):
    blocks = []
    for d in docs:
        for s in d.sections:
            blocks.append(f"## {d.title} › {s.heading}\n{s.text}")
    return "\n\n".join(blocks)

def _summarize_chunk(llm, chunk):
    msg = [{"role": "user",
            "content": f"Summarize the following source excerpt, preserving key "
                       f"facts, terminology, and steps. Excerpt from {chunk.provenance}:"
                       f"\n\n{chunk.text}"}]
    return f"### {chunk.provenance}\n{llm.generate(msg)}"

def distill(docs, llm, budget: int) -> str:
    corpus = _corpus(docs)
    if estimate_tokens(corpus) <= budget:
        return corpus
    chunks = [c for d in docs for c in chunk_document(d, max_tokens=max(500, budget // 4))]
    summaries = [_summarize_chunk(llm, c) for c in chunks]
    reduced = "\n\n".join(summaries)
    if estimate_tokens(reduced) > budget:
        msg = [{"role": "user",
                "content": f"Condense these notes to under {budget} tokens, keeping "
                           f"provenance headers:\n\n{reduced}"}]
        reduced = llm.generate(msg)
    return reduced
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_summarizer.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/process/summarizer.py tests/test_summarizer.py
git commit -m "feat: map-reduce summarizer with provenance"
```

---

## Task 7: Ingestion base + registry + detection

**Files:**
- Create: `aptitude/ingest/__init__.py`, `aptitude/ingest/base.py`
- Test: `tests/test_ingest_base.py`

**Interfaces:**
- Consumes: `Source`, `Document` (Task 1).
- Produces: ABC `IngestionAdapter` with `name:str`, `can_handle(src:Source) -> bool`, `ingest(src:Source) -> Document`. `ingest_registry = Registry("adapter")`. `detect_kind(raw:str) -> str` — `github` if host is github.com or `owner/repo` shape, `web` if starts with http, else by extension `.pdf`/`.epub`; raises `IngestionError` if unknown. `load(src:Source) -> Document` — resolves kind (honoring explicit `src.kind != "auto"`) and dispatches to the registered adapter.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_base.py
import pytest
from aptitude.models import Source
from aptitude.ingest.base import detect_kind
from aptitude.errors import IngestionError

@pytest.mark.parametrize("raw,kind", [
    ("https://github.com/a/b", "github"),
    ("octocat/hello", "github"),
    ("https://example.com/page", "web"),
    ("book.epub", "epub"),
    ("/docs/file.pdf", "pdf"),
])
def test_detect_kind(raw, kind):
    assert detect_kind(raw) == kind

def test_detect_unknown_raises():
    with pytest.raises(IngestionError):
        detect_kind("mystery.xyz")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_base.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/ingest/base.py
import re
from abc import ABC, abstractmethod
from aptitude.models import Source, Document
from aptitude.registry import Registry
from aptitude.errors import IngestionError

ingest_registry = Registry("adapter")

class IngestionAdapter(ABC):
    name: str = "base"
    @abstractmethod
    def can_handle(self, src: Source) -> bool: ...
    @abstractmethod
    def ingest(self, src: Source) -> Document: ...

def detect_kind(raw: str) -> str:
    low = raw.lower()
    if "github.com" in low or re.fullmatch(r"[\w.-]+/[\w.-]+", raw):
        return "github"
    if low.startswith("http://") or low.startswith("https://"):
        return "web"
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(".epub"):
        return "epub"
    raise IngestionError(f"cannot detect artifact type for '{raw}'")

def load(src: Source) -> Document:
    kind = src.kind if src.kind != "auto" else detect_kind(src.raw)
    return ingest_registry.get(kind)().ingest(src)
```

Create empty `aptitude/ingest/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_base.py -v`
Expected: PASS (6 params + 1).

- [ ] **Step 5: Commit**

```bash
git add aptitude/ingest/ tests/test_ingest_base.py
git commit -m "feat: ingestion adapter base, registry, type detection"
```

---

## Task 8: PDF adapter

**Files:**
- Create: `aptitude/ingest/pdf.py`
- Test: `tests/test_ingest_pdf.py`, `tests/fixtures/make_pdf.py`

**Interfaces:**
- Consumes: `IngestionAdapter`, `ingest_registry` (Task 7).
- Produces: `PdfAdapter` registered as `"pdf"`, producing one `Section` per page (`heading="Page N"`), `metadata={"pages": N}`, `title` from filename stem.

- [ ] **Step 1: Write the failing test**

```python
# tests/fixtures/make_pdf.py  (helper, imported by the test)
from pypdf import PdfWriter
def write_sample(path):
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    with open(path, "wb") as f: w.write(f)
```

```python
# tests/test_ingest_pdf.py
from pathlib import Path
from aptitude.models import Source
from aptitude.ingest.pdf import PdfAdapter
from tests.fixtures.make_pdf import write_sample

def test_pdf_produces_document(tmp_path):
    p = tmp_path / "doc.pdf"; write_sample(p)
    doc = PdfAdapter().ingest(Source(str(p), "pdf"))
    assert doc.title == "doc"
    assert doc.metadata["pages"] == 1
    assert len(doc.sections) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/ingest/pdf.py
from pathlib import Path
from pypdf import PdfReader
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

@ingest_registry.register("pdf")
class PdfAdapter(IngestionAdapter):
    name = "pdf"
    def can_handle(self, src): return src.raw.lower().endswith(".pdf")
    def ingest(self, src) -> Document:
        path = Path(src.raw)
        if not path.exists():
            raise IngestionError(f"PDF not found: {path}")
        reader = PdfReader(str(path))
        sections = [Section(f"Page {i+1}", (pg.extract_text() or "").strip())
                    for i, pg in enumerate(reader.pages)]
        return Document(src, path.stem, sections, {"pages": len(reader.pages)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_pdf.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aptitude/ingest/pdf.py tests/test_ingest_pdf.py tests/fixtures/make_pdf.py
git commit -m "feat: PDF ingestion adapter"
```

---

## Task 9: EPUB adapter

**Files:**
- Create: `aptitude/ingest/epub.py`
- Test: `tests/test_ingest_epub.py`, `tests/fixtures/make_epub.py`

**Interfaces:**
- Consumes: `IngestionAdapter`, `ingest_registry` (Task 7).
- Produces: `EpubAdapter` registered as `"epub"`; one `Section` per XHTML document item (heading = item title/name, text = stripped HTML via BeautifulSoup), `title` from book metadata, `metadata={"items": N}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/fixtures/make_epub.py
from ebooklib import epub
def write_sample(path):
    b = epub.EpubBook(); b.set_title("Sample Book")
    c = epub.EpubHtml(title="Chap 1", file_name="c1.xhtml")
    c.content = "<h1>Chapter 1</h1><p>Hello epub world.</p>"
    b.add_item(c); b.spine = [c]
    b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    epub.write_epub(str(path), b)
```

```python
# tests/test_ingest_epub.py
from aptitude.models import Source
from aptitude.ingest.epub import EpubAdapter
from tests.fixtures.make_epub import write_sample

def test_epub_extracts_text(tmp_path):
    p = tmp_path / "b.epub"; write_sample(p)
    doc = EpubAdapter().ingest(Source(str(p), "epub"))
    assert doc.title == "Sample Book"
    assert any("Hello epub world" in s.text for s in doc.sections)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_epub.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/ingest/epub.py
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

@ingest_registry.register("epub")
class EpubAdapter(IngestionAdapter):
    name = "epub"
    def can_handle(self, src): return src.raw.lower().endswith(".epub")
    def ingest(self, src) -> Document:
        try:
            book = epub.read_epub(src.raw)
        except Exception as e:
            raise IngestionError(f"cannot read EPUB {src.raw}: {e}") from e
        title = (book.get_metadata("DC", "title") or [("Untitled",)])[0][0]
        sections = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            text = BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True)
            if text:
                sections.append(Section(item.get_name(), text))
        return Document(src, title, sections, {"items": len(sections)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_epub.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aptitude/ingest/epub.py tests/test_ingest_epub.py tests/fixtures/make_epub.py
git commit -m "feat: EPUB ingestion adapter"
```

---

## Task 10: Web adapter

**Files:**
- Create: `aptitude/ingest/web.py`
- Test: `tests/test_ingest_web.py`

**Interfaces:**
- Consumes: `IngestionAdapter`, `ingest_registry` (Task 7).
- Produces: `WebAdapter(fetch=None)` registered as `"web"`; `fetch` is an injectable `Callable[[str], str]` returning HTML (defaults to an httpx GET) so tests avoid network. Extracts main content: drops `script/style/nav/footer/header/aside`, uses `<main>`/`<article>` if present, else `<body>`; `title` from `<title>`/`<h1>`. One `Section("Content", text)`. `metadata={"url": raw}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_web.py
from aptitude.models import Source
from aptitude.ingest.web import WebAdapter

HTML = """<html><head><title>My Page</title></head>
<body><nav>menu junk</nav><main><h1>Heading</h1><p>Real content here.</p></main>
<footer>footer junk</footer></body></html>"""

def test_web_extracts_main_content():
    doc = WebAdapter(fetch=lambda url: HTML).ingest(Source("https://x.test", "web"))
    assert doc.title == "My Page"
    body = " ".join(s.text for s in doc.sections)
    assert "Real content here." in body
    assert "menu junk" not in body and "footer junk" not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_web.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/ingest/web.py
import httpx
from bs4 import BeautifulSoup
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

def _default_fetch(url: str) -> str:
    r = httpx.get(url, follow_redirects=True, timeout=30,
                  headers={"User-Agent": "Aptitude/0.1"})
    r.raise_for_status()
    return r.text

@ingest_registry.register("web")
class WebAdapter(IngestionAdapter):
    name = "web"
    def __init__(self, fetch=None):
        self._fetch = fetch or _default_fetch
    def can_handle(self, src): return src.raw.lower().startswith("http")
    def ingest(self, src) -> Document:
        try:
            html = self._fetch(src.raw)
        except Exception as e:
            raise IngestionError(f"cannot fetch {src.raw}: {e}") from e
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        title = (soup.title.string if soup.title else None) or \
                (soup.h1.get_text(strip=True) if soup.h1 else src.raw)
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = main.get_text("\n", strip=True)
        return Document(src, title.strip(), [Section("Content", text)], {"url": src.raw})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_web.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aptitude/ingest/web.py tests/test_ingest_web.py
git commit -m "feat: web page ingestion adapter (injectable fetch)"
```

---

## Task 11: GitHub adapter

**Files:**
- Create: `aptitude/ingest/github.py`
- Test: `tests/test_ingest_github.py`

**Interfaces:**
- Consumes: `IngestionAdapter`, `ingest_registry` (Task 7).
- Produces: `GithubAdapter(clone=None)` registered as `"github"`; `clone` is an injectable `Callable[[str], Path]` returning a local checkout dir (defaults to `git clone --depth 1` into the cache) so tests pass a fixture dir. Reads `README*` (full), other docs (`*.md` under docs/, first 4000 chars each), and builds a **code structure** section: for each `.py`/`.js`/`.ts` file, list its path and top-level `def`/`class`/`function`/`export` signature lines (regex, no execution). `title` = repo dir name. `metadata={"files": N}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_github.py
from pathlib import Path
from aptitude.models import Source
from aptitude.ingest.github import GithubAdapter

def _make_repo(root: Path):
    (root / "README.md").write_text("# Cool Repo\nDoes cool things.")
    (root / "app.py").write_text("import os\n\ndef run(x):\n    return x\n\nclass Engine:\n    pass\n")
    return root

def test_github_reads_readme_and_signatures(tmp_path):
    repo = _make_repo(tmp_path / "cool-repo"); repo.mkdir(parents=True, exist_ok=True)
    _make_repo(repo)
    doc = GithubAdapter(clone=lambda raw: repo).ingest(Source("owner/cool-repo", "github"))
    text = "\n".join(s.text for s in doc.sections)
    assert "Does cool things." in text
    assert "def run(x)" in text and "class Engine" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_github.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/ingest/github.py
import re, subprocess, tempfile
from pathlib import Path
from aptitude.models import Source, Document, Section
from aptitude.ingest.base import IngestionAdapter, ingest_registry
from aptitude.errors import IngestionError

_SIG = re.compile(r"^\s*(def |class |function |export (default )?|async def )", re.M)
_CODE_EXT = {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java"}

def _default_clone(raw: str) -> Path:
    url = raw if raw.startswith("http") else f"https://github.com/{raw}.git"
    dest = Path(tempfile.mkdtemp(prefix="aptitude-repo-"))
    r = subprocess.run(["git", "clone", "--depth", "1", url, str(dest)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise IngestionError(f"git clone failed for {raw}: {r.stderr.strip()}")
    return dest

@ingest_registry.register("github")
class GithubAdapter(IngestionAdapter):
    name = "github"
    def __init__(self, clone=None):
        self._clone = clone or _default_clone
    def can_handle(self, src):
        return "github.com" in src.raw or bool(re.fullmatch(r"[\w.-]+/[\w.-]+", src.raw))
    def ingest(self, src) -> Document:
        root = Path(self._clone(src.raw))
        sections, n = [], 0
        for readme in sorted(root.glob("README*")):
            sections.append(Section(readme.name, readme.read_text(errors="ignore")))
        sigs = []
        for f in sorted(root.rglob("*")):
            if f.suffix in _CODE_EXT and ".git" not in f.parts:
                n += 1
                lines = [ln.strip() for ln in f.read_text(errors="ignore").splitlines()
                         if _SIG.match(ln)]
                if lines:
                    sigs.append(f"{f.relative_to(root)}:\n  " + "\n  ".join(lines))
        if sigs:
            sections.append(Section("Code structure", "\n\n".join(sigs)))
        if not sections:
            raise IngestionError(f"no readable content in repo {src.raw}")
        return Document(src, root.name, sections, {"files": n})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_github.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aptitude/ingest/github.py tests/test_ingest_github.py
git commit -m "feat: GitHub repo ingestion adapter (injectable clone)"
```

---

## Task 12: Synthesizer base + prompts + template synthesizer

**Files:**
- Create: `aptitude/synthesize/__init__.py`, `aptitude/synthesize/base.py`, `aptitude/synthesize/prompts.py`, `aptitude/synthesize/template_synth.py`
- Test: `tests/test_template_synth.py`

**Interfaces:**
- Consumes: `Document` (Task 1), `LLMProvider` (Task 4), `distill` (Task 6), `SkillDraft`/`SkillFile` (Task 1).
- Produces: ABC `Synthesizer.synthesize(prompt:str, docs:list[Document], llm:LLMProvider) -> SkillDraft`; `synth_registry = Registry("synth")`. `TemplateSynthesizer(budget:int=6000)` registered as `"template"`. It calls the LLM three times — (1) name+description as `name: <kebab>\ndescription: <text>`, (2) body markdown, (3) one references doc — parsing the name/description response with a small regex. `prompts.py` holds the three prompt templates as functions returning message lists.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_template_synth.py
from aptitude.models import Document, Source, Section
from aptitude.llm.fake import FakeProvider
from aptitude.synthesize.template_synth import TemplateSynthesizer

def _docs(): return [Document(Source("x"), "T", [Section("H", "content about privacy")])]

def test_synthesize_builds_draft():
    llm = FakeProvider(responses=[
        "name: privacy-policy-drafter\ndescription: Use when drafting GDPR privacy policies.",
        "## Instructions\nDo the thing.",
        "Reference material about GDPR.",
    ])
    draft = TemplateSynthesizer().synthesize("make a privacy skill", _docs(), llm)
    assert draft.name == "privacy-policy-drafter"
    assert "GDPR" in draft.description
    assert "Do the thing." in draft.body
    assert draft.references and "GDPR" in draft.references[0].content
    assert draft.provenance == ["x"]

def test_name_is_slugified_if_model_returns_spaces():
    llm = FakeProvider(responses=[
        "name: Privacy Policy Drafter\ndescription: d", "body", "ref"])
    draft = TemplateSynthesizer().synthesize("p", _docs(), llm)
    assert draft.name == "privacy-policy-drafter"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_template_synth.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/synthesize/base.py
from abc import ABC, abstractmethod
from aptitude.registry import Registry
from aptitude.models import Document, SkillDraft

synth_registry = Registry("synth")

class Synthesizer(ABC):
    name: str = "base"
    @abstractmethod
    def synthesize(self, prompt: str, docs: list[Document], llm) -> SkillDraft: ...
```

```python
# aptitude/synthesize/prompts.py
def name_desc_prompt(user_prompt, corpus):
    return [{"role": "user", "content":
        "You are creating a reusable AI skill. Based on the user's goal and the source "
        "material, output exactly two lines:\nname: <kebab-case-slug, max 64 chars>\n"
        f"description: <one line 'Use when…' trigger, max 1024 chars>\n\n"
        f"USER GOAL:\n{user_prompt}\n\nSOURCE MATERIAL:\n{corpus[:6000]}"}]

def body_prompt(user_prompt, corpus):
    return [{"role": "user", "content":
        "Write the body of a skill as markdown instructions that an AI assistant will "
        "follow to accomplish the user's goal, grounded in the source material. Be "
        f"concrete and actionable.\n\nUSER GOAL:\n{user_prompt}\n\nSOURCE:\n{corpus[:8000]}"}]

def reference_prompt(user_prompt, corpus):
    return [{"role": "user", "content":
        "Distill the source material into a concise reference document (facts, "
        "terminology, procedures) that supports the skill. Markdown.\n\n"
        f"GOAL:\n{user_prompt}\n\nSOURCE:\n{corpus[:8000]}"}]
```

```python
# aptitude/synthesize/template_synth.py
import re
from aptitude.models import SkillDraft, SkillFile
from aptitude.synthesize.base import Synthesizer, synth_registry
from aptitude.synthesize import prompts
from aptitude.process.summarizer import distill

def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return s[:64] or "generated-skill"

@synth_registry.register("template")
class TemplateSynthesizer(Synthesizer):
    name = "template"
    def __init__(self, budget: int = 6000):
        self.budget = budget
    def synthesize(self, prompt, docs, llm) -> SkillDraft:
        corpus = distill(docs, llm, self.budget)
        nd = llm.generate(prompts.name_desc_prompt(prompt, corpus))
        name = _slug(re.search(r"name:\s*(.+)", nd).group(1) if re.search(r"name:", nd) else "skill")
        desc_m = re.search(r"description:\s*(.+)", nd, re.S)
        description = (desc_m.group(1).strip() if desc_m else prompt)[:1024]
        body = llm.generate(prompts.body_prompt(prompt, corpus)).strip()
        ref = llm.generate(prompts.reference_prompt(prompt, corpus)).strip()
        return SkillDraft(
            name=name, description=description, body=body,
            references=[SkillFile("references/source-material.md", ref)],
            provenance=[d.source.raw for d in docs])
```

Create empty `aptitude/synthesize/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_template_synth.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/synthesize/ tests/test_template_synth.py
git commit -m "feat: template synthesizer producing SkillDraft"
```

---

## Task 13: Exporter base + registry + claude_skill exporter

**Files:**
- Create: `aptitude/export/__init__.py`, `aptitude/export/base.py`, `aptitude/export/claude_skill.py`
- Test: `tests/export_contract.py`, `tests/test_export_claude_skill.py`

**Interfaces:**
- Consumes: `SkillDraft`, `SkillFile` (Task 1).
- Produces: ABC `Exporter.export(draft:SkillDraft, out_dir:Path) -> list[Path]` with `name:str`; `export_registry = Registry("exporter")`. `ClaudeSkillExporter` registered as `"claude-skill"` writes `<out_dir>/<name>/SKILL.md` (YAML frontmatter `name`, `description`, then body) plus each reference/script file. Shared `assert_exporter_contract(exporter, draft, tmp_path)` in `tests/export_contract.py` (returns non-empty path list, all paths exist).

- [ ] **Step 1: Write the failing test**

```python
# tests/export_contract.py
def assert_exporter_contract(exporter, draft, tmp_path):
    paths = exporter.export(draft, tmp_path)
    assert paths and all(p.exists() for p in paths)
    return paths

# tests/test_export_claude_skill.py
from aptitude.models import SkillDraft, SkillFile
from aptitude.export.claude_skill import ClaudeSkillExporter
from tests.export_contract import assert_exporter_contract

def _draft():
    return SkillDraft(name="my-skill", description="Use when testing.",
                      body="## Steps\nDo it.",
                      references=[SkillFile("references/r.md", "ref body")])

def test_claude_skill_layout(tmp_path):
    paths = assert_exporter_contract(ClaudeSkillExporter(), _draft(), tmp_path)
    skill_md = (tmp_path / "my-skill" / "SKILL.md").read_text()
    assert skill_md.startswith("---\n")
    assert "name: my-skill" in skill_md and "description: Use when testing." in skill_md
    assert "## Steps" in skill_md
    assert (tmp_path / "my-skill" / "references" / "r.md").read_text() == "ref body"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_claude_skill.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/export/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from aptitude.registry import Registry
from aptitude.models import SkillDraft

export_registry = Registry("exporter")

class Exporter(ABC):
    name: str = "base"
    @abstractmethod
    def export(self, draft: SkillDraft, out_dir: Path) -> list[Path]: ...
```

```python
# aptitude/export/claude_skill.py
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.models import SkillDraft

def _yaml_escape(v: str) -> str:
    return v.replace("\n", " ").strip()

@export_registry.register("claude-skill")
class ClaudeSkillExporter(Exporter):
    name = "claude-skill"
    def export(self, draft: SkillDraft, out_dir: Path) -> list[Path]:
        root = Path(out_dir) / draft.name
        root.mkdir(parents=True, exist_ok=True)
        fm = (f"---\nname: {draft.name}\n"
              f"description: {_yaml_escape(draft.description)}\n---\n\n")
        skill_md = root / "SKILL.md"
        skill_md.write_text(fm + draft.body + "\n")
        written = [skill_md]
        for f in [*draft.references, *draft.scripts]:
            fp = root / f.relpath
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(f.content)
            written.append(fp)
        return written
```

Create empty `aptitude/export/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_claude_skill.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aptitude/export/ tests/export_contract.py tests/test_export_claude_skill.py
git commit -m "feat: exporter base + Claude Code SKILL.md exporter"
```

---

## Task 14: generic_prompt + local_llm exporters

**Files:**
- Create: `aptitude/export/generic_prompt.py`, `aptitude/export/local_llm.py`
- Test: `tests/test_export_generic_local.py`

**Interfaces:**
- Consumes: exporter base (Task 13), `SkillDraft` (Task 1).
- Produces: `GenericPromptExporter` registered as `"generic-prompt"` → `<out>/<name>/<name>.md` (description + body + inlined references) and `<name>.json` (`{"name","description","system_prompt"}`). `LocalLlmExporter` registered as `"local-llm"` → `<out>/<name>/Modelfile` (`FROM llama3.1` + `SYSTEM """…"""`) and `system.txt` (plain system prompt).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_generic_local.py
import json
from aptitude.models import SkillDraft, SkillFile
from aptitude.export.generic_prompt import GenericPromptExporter
from aptitude.export.local_llm import LocalLlmExporter

def _draft():
    return SkillDraft(name="s", description="Use when X.", body="Body here.",
                      references=[SkillFile("references/r.md", "REF")])

def test_generic_prompt_md_and_json(tmp_path):
    GenericPromptExporter().export(_draft(), tmp_path)
    md = (tmp_path / "s" / "s.md").read_text()
    assert "Body here." in md and "REF" in md
    data = json.loads((tmp_path / "s" / "s.json").read_text())
    assert data["name"] == "s" and "Body here." in data["system_prompt"]

def test_local_llm_modelfile_and_system(tmp_path):
    LocalLlmExporter().export(_draft(), tmp_path)
    mf = (tmp_path / "s" / "Modelfile").read_text()
    assert mf.startswith("FROM ") and "SYSTEM" in mf
    assert "Body here." in (tmp_path / "s" / "system.txt").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_generic_local.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/export/generic_prompt.py
import json
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.models import SkillDraft

def _system_prompt(draft: SkillDraft) -> str:
    refs = "\n\n".join(f"# {f.relpath}\n{f.content}" for f in draft.references)
    parts = [draft.description, "", draft.body]
    if refs:
        parts += ["", "## Reference material", refs]
    return "\n".join(parts).strip()

@export_registry.register("generic-prompt")
class GenericPromptExporter(Exporter):
    name = "generic-prompt"
    def export(self, draft, out_dir) -> list[Path]:
        root = Path(out_dir) / draft.name; root.mkdir(parents=True, exist_ok=True)
        sysp = _system_prompt(draft)
        md = root / f"{draft.name}.md"; md.write_text(f"# {draft.name}\n\n{sysp}\n")
        js = root / f"{draft.name}.json"
        js.write_text(json.dumps({"name": draft.name, "description": draft.description,
                                  "system_prompt": sysp}, indent=2))
        return [md, js]
```

```python
# aptitude/export/local_llm.py
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.export.generic_prompt import _system_prompt

@export_registry.register("local-llm")
class LocalLlmExporter(Exporter):
    name = "local-llm"
    def export(self, draft, out_dir) -> list[Path]:
        root = Path(out_dir) / draft.name; root.mkdir(parents=True, exist_ok=True)
        sysp = _system_prompt(draft)
        mf = root / "Modelfile"
        mf.write_text(f'FROM llama3.1\nSYSTEM """\n{sysp}\n"""\n')
        st = root / "system.txt"; st.write_text(sysp + "\n")
        return [mf, st]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_generic_local.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/export/generic_prompt.py aptitude/export/local_llm.py tests/test_export_generic_local.py
git commit -m "feat: generic-prompt and local-llm exporters"
```

---

## Task 15: mcp_manifest + packager exporters

**Files:**
- Create: `aptitude/export/mcp_manifest.py`, `aptitude/export/packager.py`
- Test: `tests/test_export_mcp_packager.py`

**Interfaces:**
- Consumes: exporter base (Task 13), `ClaudeSkillExporter` (Task 13), `SkillDraft`/`ToolSpec` (Task 1).
- Produces: `McpManifestExporter` registered as `"mcp-manifest"` → `<out>/<name>/mcp.json` (`{"tools":[{name,description,parameters}…]}`); returns `[]` (writes nothing) when `draft.tools` is empty. `ZipPackager` registered as `"zip"` → first runs `ClaudeSkillExporter`, then zips `<out>/<name>/` into `<out>/<name>.zip`; returns `[zip_path]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_mcp_packager.py
import json, zipfile
from aptitude.models import SkillDraft, ToolSpec
from aptitude.export.mcp_manifest import McpManifestExporter
from aptitude.export.packager import ZipPackager

def test_mcp_manifest_only_when_tools(tmp_path):
    no_tools = SkillDraft(name="s", description="d", body="b")
    assert McpManifestExporter().export(no_tools, tmp_path) == []
    with_tools = SkillDraft(name="s", description="d", body="b",
                            tools=[ToolSpec("run", "runs it", {"type": "object"})])
    paths = McpManifestExporter().export(with_tools, tmp_path)
    data = json.loads(paths[0].read_text())
    assert data["tools"][0]["name"] == "run"

def test_zip_packager_bundles_skill(tmp_path):
    draft = SkillDraft(name="s", description="d", body="b")
    paths = ZipPackager().export(draft, tmp_path)
    assert paths[0].suffix == ".zip"
    with zipfile.ZipFile(paths[0]) as z:
        assert any(n.endswith("SKILL.md") for n in z.namelist())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_mcp_packager.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/export/mcp_manifest.py
import json
from pathlib import Path
from aptitude.export.base import Exporter, export_registry

@export_registry.register("mcp-manifest")
class McpManifestExporter(Exporter):
    name = "mcp-manifest"
    def export(self, draft, out_dir) -> list[Path]:
        if not draft.tools:
            return []
        root = Path(out_dir) / draft.name; root.mkdir(parents=True, exist_ok=True)
        manifest = {"tools": [{"name": t.name, "description": t.description,
                               "parameters": t.parameters} for t in draft.tools]}
        p = root / "mcp.json"; p.write_text(json.dumps(manifest, indent=2))
        return [p]
```

```python
# aptitude/export/packager.py
import zipfile
from pathlib import Path
from aptitude.export.base import Exporter, export_registry
from aptitude.export.claude_skill import ClaudeSkillExporter

@export_registry.register("zip")
class ZipPackager(Exporter):
    name = "zip"
    def export(self, draft, out_dir) -> list[Path]:
        out_dir = Path(out_dir)
        ClaudeSkillExporter().export(draft, out_dir)
        skill_dir = out_dir / draft.name
        zip_path = out_dir / f"{draft.name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in skill_dir.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(out_dir))
        return [zip_path]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_mcp_packager.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/export/mcp_manifest.py aptitude/export/packager.py tests/test_export_mcp_packager.py
git commit -m "feat: MCP manifest and zip packager exporters"
```

---

## Task 16: Validator

**Files:**
- Create: `aptitude/validate/__init__.py`, `aptitude/validate/validator.py`
- Test: `tests/test_validator.py`

**Interfaces:**
- Consumes: `SkillDraft` (Task 1), `ValidationError` (Task 1).
- Produces: `validate_draft(draft:SkillDraft) -> list[str]` (returns warnings; raises `ValidationError` on hard failures: bad name pattern, name >64, empty description, description >1024). `validate_skill_dir(path:Path) -> list[str]` — parses a `SKILL.md`'s frontmatter and validates `name`/`description`; raises `ValidationError` if `SKILL.md` missing or frontmatter absent.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validator.py
import pytest
from aptitude.models import SkillDraft
from aptitude.validate.validator import validate_draft, validate_skill_dir
from aptitude.errors import ValidationError

def test_valid_draft_no_error():
    assert validate_draft(SkillDraft("good-name", "Use when X.", "body")) == []

def test_bad_name_raises():
    with pytest.raises(ValidationError):
        validate_draft(SkillDraft("Bad Name!", "d", "b"))

def test_empty_description_raises():
    with pytest.raises(ValidationError):
        validate_draft(SkillDraft("n", "", "b"))

def test_validate_skill_dir(tmp_path):
    d = tmp_path / "n"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: n\ndescription: Use when X.\n---\nbody")
    assert validate_skill_dir(d) == []
    (d / "SKILL.md").write_text("no frontmatter")
    with pytest.raises(ValidationError):
        validate_skill_dir(d)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validator.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/validate/validator.py
import re
from pathlib import Path
from aptitude.models import SkillDraft
from aptitude.errors import ValidationError

_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

def validate_draft(draft: SkillDraft) -> list[str]:
    if not _NAME.match(draft.name) or len(draft.name) > 64:
        raise ValidationError(f"invalid skill name '{draft.name}'")
    if not draft.description.strip():
        raise ValidationError("description must not be empty")
    if len(draft.description) > 1024:
        raise ValidationError("description exceeds 1024 chars")
    warnings = []
    if len(draft.body) < 40:
        warnings.append("body is very short; skill may be low quality")
    return warnings

def validate_skill_dir(path: Path) -> list[str]:
    skill = Path(path) / "SKILL.md"
    if not skill.exists():
        raise ValidationError(f"no SKILL.md in {path}")
    text = skill.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValidationError("SKILL.md missing YAML frontmatter")
    fm = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M))
    return validate_draft(SkillDraft(fm.get("name", ""), fm.get("description", ""),
                                     text[m.end():]))
```

Create empty `aptitude/validate/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validator.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/validate/ tests/test_validator.py
git commit -m "feat: skill draft and SKILL.md directory validation"
```

---

## Task 17: OpenAI-compatible providers (base + openai + nvidia)

**Files:**
- Create: `aptitude/llm/openai.py`
- Test: `tests/test_llm_openai.py`

**Interfaces:**
- Consumes: `LLMProvider`, `provider_registry` (Task 4), `ProviderError` (Task 1).
- Produces: `OpenAICompatibleProvider(model, api_key, base_url, context_window=8000, client=None)` — POSTs `{model, messages}` to `{base_url}/chat/completions`, returns `choices[0].message.content`; raises `ProviderError` on non-2xx. `client` is an injectable `httpx.Client` (tests pass one built on `httpx.MockTransport`). `OpenAIProvider` registered `"openai"` (base_url `https://api.openai.com/v1`), `NvidiaProvider` registered `"nvidia"` (base_url `https://integrate.api.nvidia.com/v1`). Both read key + model in a `build(cfg, env)` classmethod.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_openai.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_openai.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/llm/openai.py
import httpx
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"
    def __init__(self, model, api_key, base_url, context_window=8000, client=None):
        self.model, self.api_key = model, api_key
        self.base_url = base_url.rstrip("/")
        self.context_window = context_window
        self._client = client or httpx.Client(timeout=120)
    def generate(self, messages, **opts) -> str:
        r = self._client.post(f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, **opts})
        if r.status_code // 100 != 2:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"]

@provider_registry.register("openai")
class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["openai"],
                   api_key_for("openai", env),
                   cfg.get("base_url") or "https://api.openai.com/v1")

@provider_registry.register("nvidia")
class NvidiaProvider(OpenAICompatibleProvider):
    name = "nvidia"
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["nvidia"],
                   api_key_for("nvidia", env),
                   cfg.get("base_url") or "https://integrate.api.nvidia.com/v1")
```

Add `from aptitude.llm import openai  # noqa` to `aptitude/llm/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_openai.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/openai.py aptitude/llm/__init__.py tests/test_llm_openai.py
git commit -m "feat: OpenAI-compatible providers (openai, nvidia)"
```

---

## Task 18: Ollama + Claude + Gemini providers

**Files:**
- Create: `aptitude/llm/ollama.py`, `aptitude/llm/claude.py`, `aptitude/llm/gemini.py`
- Test: `tests/test_llm_ollama.py`, `tests/test_llm_claude_gemini.py`

**Interfaces:**
- Consumes: `LLMProvider`, `provider_registry` (Task 4), `ProviderError` (Task 1).
- Produces: `OllamaProvider(model, base_url="http://localhost:11434", client=None)` — POSTs to `{base_url}/api/chat` with `{model, messages, stream:False}`, returns `message.content`. `ClaudeProvider(model, api_key, client=None)` and `GeminiProvider(model, api_key, client=None)` — each takes an injectable `client` exposing a `.generate(model, messages) -> str` seam so tests inject a fake and real code lazily builds the SDK client. All expose `build(cfg, env)`.

**IMPLEMENTER NOTE:** Before writing `claude.py`, invoke the `claude-api` skill and confirm the current Claude model IDs; update `DEFAULT_MODELS["claude"]` in `aptitude/config.py` accordingly (the value committed in Task 3 is a placeholder).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_ollama.py
import httpx
from aptitude.llm.ollama import OllamaProvider

def test_ollama_parses_chat_response():
    def handler(req):
        return httpx.Response(200, json={"message": {"content": "local reply"}})
    p = OllamaProvider("llama3.1", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.generate([{"role": "user", "content": "hi"}]) == "local reply"
```

```python
# tests/test_llm_claude_gemini.py
from aptitude.llm.claude import ClaudeProvider
from aptitude.llm.gemini import GeminiProvider

class _FakeClient:
    def generate(self, model, messages, **opts): return "sdk reply"

def test_claude_uses_injected_client():
    assert ClaudeProvider("m", "key", client=_FakeClient()).generate(
        [{"role": "user", "content": "x"}]) == "sdk reply"

def test_gemini_uses_injected_client():
    assert GeminiProvider("m", "key", client=_FakeClient()).generate(
        [{"role": "user", "content": "x"}]) == "sdk reply"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_ollama.py tests/test_llm_claude_gemini.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/llm/ollama.py
import httpx
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import DEFAULT_MODELS

@provider_registry.register("ollama")
class OllamaProvider(LLMProvider):
    name = "ollama"
    def __init__(self, model, base_url="http://localhost:11434", client=None):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.context_window = 8000
        self._client = client or httpx.Client(timeout=300)
    def generate(self, messages, **opts) -> str:
        try:
            r = self._client.post(f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False})
        except Exception as e:
            raise ProviderError(f"Ollama unreachable at {self.base_url}: {e}") from e
        if r.status_code // 100 != 2:
            raise ProviderError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["message"]["content"]
    @classmethod
    def build(cls, cfg, env):
        return cls(cfg.get("model") or DEFAULT_MODELS["ollama"],
                   cfg.get("base_url") or "http://localhost:11434")
```

```python
# aptitude/llm/claude.py
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

class _AnthropicClient:  # lazy real client
    def __init__(self, api_key):
        import anthropic
        self._c = anthropic.Anthropic(api_key=api_key)
    def generate(self, model, messages, **opts):
        sys = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [m for m in messages if m["role"] != "system"]
        resp = self._c.messages.create(model=model, max_tokens=opts.get("max_tokens", 4096),
                                       system=sys or None, messages=conv)
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

@provider_registry.register("claude")
class ClaudeProvider(LLMProvider):
    name = "claude"
    def __init__(self, model, api_key, client=None):
        self.model, self.context_window = model, 200000
        self._client = client or _AnthropicClient(api_key)
    def generate(self, messages, **opts) -> str:
        try:
            return self._client.generate(self.model, messages, **opts)
        except Exception as e:
            raise ProviderError(f"Claude call failed: {e}") from e
    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("claude", env)
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["claude"], key)
```

```python
# aptitude/llm/gemini.py
from aptitude.llm.base import LLMProvider, provider_registry
from aptitude.errors import ProviderError
from aptitude.config import api_key_for, DEFAULT_MODELS

class _GeminiClient:
    def __init__(self, api_key):
        from google import genai
        self._c = genai.Client(api_key=api_key)
    def generate(self, model, messages, **opts):
        text = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        return self._c.models.generate_content(model=model, contents=text).text

@provider_registry.register("gemini")
class GeminiProvider(LLMProvider):
    name = "gemini"
    def __init__(self, model, api_key, client=None):
        self.model, self.context_window = model, 1000000
        self._client = client or _GeminiClient(api_key)
    def generate(self, messages, **opts) -> str:
        try:
            return self._client.generate(self.model, messages, **opts)
        except Exception as e:
            raise ProviderError(f"Gemini call failed: {e}") from e
    @classmethod
    def build(cls, cfg, env):
        key = api_key_for("gemini", env)
        if not key:
            raise ProviderError("GEMINI_API_KEY not set")
        return cls(cfg.get("model") or DEFAULT_MODELS["gemini"], key)
```

Add `from aptitude.llm import ollama, claude, gemini  # noqa` to `aptitude/llm/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_ollama.py tests/test_llm_claude_gemini.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/ollama.py aptitude/llm/claude.py aptitude/llm/gemini.py aptitude/llm/__init__.py tests/test_llm_ollama.py tests/test_llm_claude_gemini.py
git commit -m "feat: Ollama, Claude, Gemini providers"
```

---

## Task 19: Provider factory + pipeline orchestration

**Files:**
- Create: `aptitude/llm/factory.py`, `aptitude/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything above. `build_provider(name, cfg, env) -> LLMProvider` — for `fake` returns `FakeProvider`; for providers with a `build` classmethod calls it; else raises `ProviderError`.
- Produces: `RunConfig` dataclass (`prompt, sources:list[Source], provider, model, formats:list[str], out:Path, budget:int, dry_run:bool, synth:str="template"`). `run(cfg:RunConfig, provider:LLMProvider) -> RunResult` where `RunResult(draft, written:list[Path], skipped:list[tuple[str,str]], exit_code:int)`. Flow: load each source (collect failures, skip; abort with exit 2 if all fail), synthesize, validate, export each format into `out`. `dry_run` stops after distill and fills `draft=None`, returning the corpus in `RunResult.corpus`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from pathlib import Path
from aptitude.models import Source
from aptitude.llm.fake import FakeProvider
from aptitude.pipeline import RunConfig, run
from aptitude.ingest.base import ingest_registry, IngestionAdapter
from aptitude.models import Document, Section

class _StubAdapter(IngestionAdapter):
    name = "stub"
    def can_handle(self, src): return True
    def ingest(self, src):
        if "bad" in src.raw:
            raise Exception("boom")
        return Document(src, "T", [Section("H", "content")])

def _cfg(tmp_path, raws, dry=False):
    return RunConfig(prompt="make skill", sources=[Source(r, "stub") for r in raws],
                     provider="fake", model=None, formats=["claude-skill"],
                     out=tmp_path, budget=6000, dry_run=dry)

def test_end_to_end_writes_skill(tmp_path, monkeypatch):
    ingest_registry._items["stub"] = _StubAdapter
    llm = FakeProvider(responses=["name: my-skill\ndescription: Use when X.",
                                  "## Body", "ref"])
    res = run(_cfg(tmp_path, ["a.stub"]), llm)
    assert res.exit_code == 0
    assert (tmp_path / "my-skill" / "SKILL.md").exists()

def test_partial_failure_skips_and_continues(tmp_path):
    ingest_registry._items["stub"] = _StubAdapter
    llm = FakeProvider(responses=["name: my-skill\ndescription: Use when X.", "b", "r"])
    res = run(_cfg(tmp_path, ["bad.stub", "ok.stub"]), llm)
    assert res.exit_code == 1 and res.skipped and res.draft is not None

def test_all_fail_is_fatal(tmp_path):
    ingest_registry._items["stub"] = _StubAdapter
    res = run(_cfg(tmp_path, ["bad1.stub", "bad2.stub"]), FakeProvider())
    assert res.exit_code == 2 and res.draft is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/llm/factory.py
from aptitude.llm.base import provider_registry
from aptitude.llm.fake import FakeProvider
from aptitude.errors import ProviderError

def build_provider(name, cfg, env):
    if name == "fake":
        return FakeProvider()
    cls = provider_registry.get(name)
    if hasattr(cls, "build"):
        return cls.build(cfg, env)
    raise ProviderError(f"provider '{name}' cannot be constructed")
```

```python
# aptitude/pipeline.py
from dataclasses import dataclass, field
from pathlib import Path
from aptitude.models import Source, SkillDraft
from aptitude.ingest.base import load
from aptitude.synthesize.base import synth_registry
from aptitude.process.summarizer import distill
from aptitude.validate.validator import validate_draft
from aptitude.export.base import export_registry
import aptitude.synthesize.template_synth  # noqa  (register)
import aptitude.export.claude_skill  # noqa

@dataclass
class RunConfig:
    prompt: str
    sources: list[Source]
    provider: str
    model: str | None
    formats: list[str]
    out: Path
    budget: int = 6000
    dry_run: bool = False
    synth: str = "template"

@dataclass
class RunResult:
    draft: SkillDraft | None
    written: list[Path] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corpus: str | None = None
    exit_code: int = 0

def run(cfg: RunConfig, provider) -> RunResult:
    docs, skipped = [], []
    for src in cfg.sources:
        try:
            docs.append(load(src))
        except Exception as e:
            skipped.append((src.raw, str(e)))
    if not docs:
        return RunResult(draft=None, skipped=skipped, exit_code=2)
    if cfg.dry_run:
        return RunResult(draft=None, skipped=skipped,
                         corpus=distill(docs, provider, cfg.budget),
                         exit_code=1 if skipped else 0)
    synth = synth_registry.get(cfg.synth)(budget=cfg.budget)
    draft = synth.synthesize(cfg.prompt, docs, provider)
    warnings = validate_draft(draft)
    written = []
    for fmt in cfg.formats:
        written += export_registry.get(fmt)().export(draft, cfg.out)
    return RunResult(draft=draft, written=written, skipped=skipped,
                     warnings=warnings, exit_code=1 if skipped else 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aptitude/llm/factory.py aptitude/pipeline.py tests/test_pipeline.py
git commit -m "feat: provider factory and pipeline orchestration"
```

---

## Task 20: CLI

**Files:**
- Create: `aptitude/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `RunConfig`/`run` (Task 19), `build_provider` (Task 19), `resolve_config`/`default_provider` (Task 3), registries (providers/exporters), `validate_skill_dir` (Task 16).
- Produces: Typer `app` with commands: `create` (options `--prompt/-p`, `--input/-i` repeatable, `--type`, `--provider`, `--model`, `--format` (comma list; `all` expands to every registered exporter), `--out`, `--budget`, `--dry-run`, `-v`); `providers` (lists provider names + whether key present/reachable); `formats` (lists exporter names); `validate <dir>`; `init`. `create` resolves provider (explicit → config → `default_provider(env)`), builds it, runs the pipeline, prints a summary, and exits with `RunResult.exit_code`. `--prompt @file` reads prompt from a file.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from aptitude.cli import app

runner = CliRunner()

def test_formats_lists_claude_skill():
    r = runner.invoke(app, ["formats"])
    assert r.exit_code == 0 and "claude-skill" in r.output

def test_create_with_fake_provider(tmp_path, monkeypatch):
    pdf = tmp_path / "d.pdf"
    from tests.fixtures.make_pdf import write_sample; write_sample(pdf)
    r = runner.invoke(app, ["create", "-p", "make a skill", "-i", str(pdf),
                            "--provider", "fake", "--out", str(tmp_path / "out")])
    assert r.exit_code == 0
    assert list((tmp_path / "out").glob("*/SKILL.md"))

def test_validate_command(tmp_path):
    d = tmp_path / "s"; d.mkdir()
    (d / "SKILL.md").write_text("---\nname: s\ndescription: Use when X.\n---\nbody")
    r = runner.invoke(app, ["validate", str(d)])
    assert r.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# aptitude/cli.py
import os
from pathlib import Path
import typer
from aptitude import llm  # noqa  (registers providers)
from aptitude.models import Source
from aptitude.config import resolve_config, default_provider
from aptitude.llm.factory import build_provider
from aptitude.llm.base import provider_registry
from aptitude.export.base import export_registry
import aptitude.export.generic_prompt, aptitude.export.local_llm  # noqa
import aptitude.export.mcp_manifest, aptitude.export.packager  # noqa
from aptitude.pipeline import RunConfig, run
from aptitude.validate.validator import validate_skill_dir
from aptitude.errors import AptitudeError

app = typer.Typer(help="Aptitude — generate skills from artifacts.")

def _read_prompt(p: str) -> str:
    return Path(p[1:]).read_text() if p.startswith("@") else p

@app.command()
def create(prompt: str = typer.Option(..., "--prompt", "-p"),
           input: list[str] = typer.Option([], "--input", "-i"),
           type: str = typer.Option("auto", "--type"),
           provider: str = typer.Option(None, "--provider"),
           model: str = typer.Option(None, "--model"),
           format: str = typer.Option("claude-skill", "--format"),
           out: str = typer.Option("./out", "--out"),
           budget: int = typer.Option(6000, "--budget"),
           dry_run: bool = typer.Option(False, "--dry-run"),
           verbose: bool = typer.Option(False, "-v")):
    env = dict(os.environ)
    cfg = resolve_config({"provider": provider, "model": model}, env,
                         Path("aptitude.toml"))
    prov_name = cfg["provider"] or default_provider(env)
    fmts = (export_registry.names() if format == "all"
            else [f.strip() for f in format.split(",")])
    try:
        provider_obj = build_provider(prov_name, cfg, env)
        rc = RunConfig(prompt=_read_prompt(prompt),
                       sources=[Source(i, type) for i in input],
                       provider=prov_name, model=cfg.get("model"), formats=fmts,
                       out=Path(out), budget=budget, dry_run=dry_run)
        res = run(rc, provider_obj)
    except AptitudeError as e:
        typer.echo(f"error: {e}"); raise typer.Exit(2)
    for raw, why in res.skipped:
        typer.echo(f"skipped {raw}: {why}")
    if res.corpus is not None:
        typer.echo(res.corpus[:2000])
    elif res.draft:
        typer.echo(f"created '{res.draft.name}' → {len(res.written)} files in {out}")
        for w in res.warnings:
            typer.echo(f"warning: {w}")
    raise typer.Exit(res.exit_code)

@app.command()
def providers():
    env = os.environ
    from aptitude.config import api_key_for
    for name in provider_registry.names():
        state = "ready" if (name in ("ollama", "fake") or api_key_for(name, env)) else "no key"
        typer.echo(f"{name}: {state}")

@app.command()
def formats():
    for name in export_registry.names():
        typer.echo(name)

@app.command()
def validate(path: str):
    try:
        warns = validate_skill_dir(Path(path))
    except AptitudeError as e:
        typer.echo(f"invalid: {e}"); raise typer.Exit(2)
    typer.echo("valid" + ("" if not warns else f" (warnings: {warns})"))

@app.command()
def init():
    p = Path("aptitude.toml")
    if p.exists():
        typer.echo("aptitude.toml already exists"); raise typer.Exit(1)
    p.write_text('provider = "ollama"\nmodel = "llama3.1"\nformat = "claude-skill"\n')
    typer.echo("wrote aptitude.toml")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v && pytest -v`
Expected: PASS (3 CLI tests; full suite green).

- [ ] **Step 5: Commit**

```bash
git add aptitude/cli.py tests/test_cli.py
git commit -m "feat: Typer CLI (create, providers, formats, validate, init)"
```

---

## Task 21: README + end-to-end smoke doc

**Files:**
- Create: `README.md`
- Test: `tests/test_readme_examples.py` (asserts the documented CLI commands parse via Typer without executing providers)

**Interfaces:**
- Consumes: `app` (Task 20).
- Produces: `README.md` documenting install, the five providers, the five formats, config precedence, and 3 worked examples. A test invokes `--help` on each command to guard against drift.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readme_examples.py
from pathlib import Path
from typer.testing import CliRunner
from aptitude.cli import app

runner = CliRunner()

def test_all_commands_have_help():
    for cmd in ["create", "providers", "formats", "validate", "init"]:
        assert runner.invoke(app, [cmd, "--help"]).exit_code == 0

def test_readme_mentions_all_providers():
    text = Path("README.md").read_text()
    for p in ["claude", "gemini", "nvidia", "ollama", "openai"]:
        assert p in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_readme_examples.py -v`
Expected: FAIL — `FileNotFoundError: README.md`.

- [ ] **Step 3: Write README**

Write `README.md` covering: what Aptitude does; `pip install -e ".[dev]"`; the provider table (claude/gemini/nvidia/ollama/openai + required env var each); the format list (claude-skill/generic-prompt/local-llm/mcp-manifest/zip); config precedence (CLI > env > `aptitude.toml` > default); and these worked examples:

```bash
# 1. PDF → Claude skill via local Ollama
aptitude create -p "Skill for drafting GDPR privacy policies" -i privacy-law.pdf --provider ollama

# 2. Repo + web page → all formats via Claude
aptitude create -p "Skill for using our API" -i github.com/acme/sdk -i https://docs.acme.dev --provider claude --format all

# 3. Preview the distilled corpus without paying for synthesis
aptitude create -p "..." -i big-book.epub --dry-run
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_readme_examples.py -v && pytest -v`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_readme_examples.py
git commit -m "docs: README with providers, formats, and worked examples"
```

---

## Self-Review

**Spec coverage:**
- §5 module layout → Tasks 1–20 create every listed module. ✓
- §6 data model → Task 1. ✓
- §7 stage interfaces → Tasks 4 (LLM), 7 (Ingestion), 12 (Synthesizer), 13 (Exporter). ✓
- §8 data flow (ingest→process→synthesize→validate→export, caching, dry-run, partial failure) → Tasks 5/6/19; dry-run + partial-failure covered by Task 19 tests. NOTE: on-disk caching of web/github fetches is implemented via the injectable `fetch`/`clone` seams but a persistent cache layer is deferred (see Deferred, below). ✓ (partial)
- §9 provider matrix (claude/gemini/nvidia/ollama/openai + OpenAI-compatible base) → Tasks 17–18. ✓
- §10 exporters (claude-skill/generic-prompt/local-llm/mcp-manifest/zip) → Tasks 13–15. ✓
- §11 extension points → registries in Tasks 2/4/7/12/13; V2 agentic synthesizer plugs into `synth_registry` (Task 12). ✓
- §12 CLI surface → Task 20. ✓
- §13 config → Task 3. ✓
- §14 error handling (typed hierarchy, skip-one-input, exit codes) → Tasks 1/19/20. ✓
- §15 testing (fake provider, contract suites, live marker) → Tasks 4/13/17 contracts; `live` marker in Task 1 pyproject. ✓

**Deferred (documented gaps, not silent):** Persistent on-disk fetch/clone cache (`--no-cache`), provider-exact `count_tokens` beyond the char/4 heuristic, and retry/backoff on transient provider errors are intentionally out of this plan's scope; the seams exist (injectable clients/fetchers, `estimate_tokens`) so they can be added without structural change. Add a follow-up plan if desired.

**Placeholder scan:** No "TBD"/"implement later" steps; every code step has runnable code. One intentional call-out remains and is labelled: the `claude` model ID (confirm via `claude-api` skill, Task 18).

**Type consistency:** `SkillDraft` field names (`references`, `scripts`, `tools`, `provenance`), `Exporter.export(draft, out_dir) -> list[Path]`, `LLMProvider.generate(messages, **opts) -> str`, `RunConfig`/`RunResult` fields, and registry names (`fake`, `claude-skill`, `template`) are used consistently across Tasks 1→20.
