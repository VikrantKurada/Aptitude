# Aptitude — Skill Generator: Design

**Status:** Approved (design phase)
**Date:** 2026-08-03
**Owner:** VikrantKurada

## 1. Summary

Aptitude is a Python CLI tool that generates reusable **skills** for Claude Code and
other GenAI applications. A user supplies a natural-language **prompt** (the intent)
plus one or more **artifacts** (PDF, EPUB, web page, or GitHub repo). Aptitude ingests
the artifacts, distills them with a user-chosen LLM provider, and emits a skill in one
or more output formats.

Example invocation:

```bash
aptitude create \
  --prompt "Build a skill for drafting GDPR-compliant privacy policies" \
  --input privacy-law.pdf \
  --input https://gdpr.eu/what-is-gdpr/ \
  --input github.com/some/repo \
  --provider ollama --model llama3.1 \
  --format claude-skill,generic-prompt \
  --out ./out
```

## 2. Goals

- Turn heterogeneous source artifacts + a prompt into a high-quality, reusable skill.
- Support multiple LLM providers, pluggably: Claude, Gemini, NVIDIA NIM, local Ollama,
  and any OpenAI-compatible endpoint (OpenAI, LM Studio, vLLM, …).
- Support multiple output formats, pluggably: Claude Code `SKILL.md` package, generic
  system-prompt bundle, local-LLM form (Ollama Modelfile / plain system prompt),
  MCP tool manifest, and a distributable `.zip`.
- Handle large sources (big PDFs, whole repos) via smart extraction + map-reduce
  summarization that respects the active provider's context budget.
- Be deterministic and unit-testable; extension never requires touching the pipeline.

## 3. Non-goals (v1)

- Agentic synthesis (an LLM agent autonomously assembling the skill). **Deferred to
  V2**; the architecture reserves a plug-in point for it (see §11).
- A web UI or hosted service. CLI only.
- Deep website crawling and full-source-tree analysis. v1 uses smart extraction
  (main content per page; README/docs + code structure/signatures for repos).
- Automated publishing/installation into a live Claude Code environment.

## 4. Approach

Chosen approach: **pluggable pipeline** (a linear `Ingest → Process → Synthesize →
Export` flow, each stage a registry of interchangeable components behind clean ABCs).

Rejected alternatives:

- **Monolithic orchestrator** — fewer abstractions, faster to start, but ages badly
  with 5 providers and 5 output formats; poor testability.
- **Agentic synthesis** — flexible but nondeterministic, costlier, and tool-calling
  support is uneven across Ollama/NVIDIA. Deferred to V2 as an optional mode.

## 5. Architecture & module layout

Every stage boundary is an ABC plus a registry keyed by a string name. The CLI selects
components by name (`--provider ollama`, `--format claude-skill,generic`), so adding a
provider or format is a drop-in and never touches `pipeline.py`.

```
aptitude/
  cli.py              # Typer app: parse args, build a RunConfig, invoke the pipeline
  config.py           # Layered config: CLI flags > env vars > config file > defaults
  pipeline.py         # Orchestrates Ingest -> Process -> Synthesize -> Export
  models.py           # Core dataclasses: Source, Document, Section, Chunk,
                      #   SkillDraft, SkillFile, ToolSpec
  errors.py           # Exception hierarchy

  ingest/
    base.py           # IngestionAdapter ABC + registry + auto source-type detection
    pdf.py  epub.py  web.py  github.py

  process/
    tokens.py         # provider-aware token counting
    chunker.py        # token-aware splitting
    summarizer.py     # map-reduce summarization when a Document exceeds context budget

  llm/
    base.py           # LLMProvider ABC + registry (generate, context_window,
                      #   count_tokens, capabilities)
    claude.py  gemini.py  nvidia.py  ollama.py  openai.py

  synthesize/
    base.py           # Synthesizer ABC   <- V2 agentic synthesizer plugs in here
    template_synth.py # v1: structured, prompt-driven synthesis
    prompts.py        # meta-prompts that generate each skill section

  export/
    base.py           # Exporter ABC + registry
    claude_skill.py  generic_prompt.py  local_llm.py  mcp_manifest.py  packager.py

  validate/
    validator.py      # frontmatter/name/description checks; per-format validation

tests/                # unit tests per adapter/provider/exporter + pipeline integration
pyproject.toml  README.md
```

## 6. Core data model

The objects that flow between stages (`models.py`):

```python
@dataclass
class Source:            # one user-provided artifact
    raw: str                     # path or URL
    kind: Literal["pdf", "epub", "web", "github", "auto"]

@dataclass
class Section:
    heading: str
    text: str
    code: str | None = None

@dataclass
class Document:         # normalized output of any ingestion adapter
    source: Source
    title: str
    sections: list[Section]      # ordered
    metadata: dict               # author, url, repo stats, page count, etc.

@dataclass
class Chunk:            # token-bounded slice of one or more sections
    text: str
    token_count: int
    provenance: str              # e.g. "privacy-law.pdf > §3 Data Subject Rights"

@dataclass
class SkillFile:
    relpath: str                 # path within the exported skill package
    content: str

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict             # JSON-schema-ish

@dataclass
class SkillDraft:      # format-neutral synthesized skill — the pivot object
    name: str                    # kebab-case, validated
    description: str             # the "use when..." trigger line
    body: str                    # main instructions (markdown)
    references: list[SkillFile]  # supporting docs distilled from sources
    scripts: list[SkillFile]     # optional helper scripts the skill mentions
    tools: list[ToolSpec]        # optional; feeds the MCP manifest exporter
    provenance: list[str]        # which sources informed this skill
```

`SkillDraft` is the **pivot**: every synthesizer produces one, every exporter consumes
one. This is what keeps providers and formats independent of each other.

## 7. Stage interfaces

Each is an ABC with a `name` attribute plus one core method:

- `IngestionAdapter.ingest(Source) -> Document`; source-type auto-detection is handled
  centrally by `detect_kind()` + the adapter registry (not per-adapter).
- `LLMProvider.generate(messages, **opts) -> str`, plus `context_window: int`,
  `count_tokens(text) -> int`, and a `capabilities` descriptor.
- `Synthesizer.synthesize(prompt, docs: list[Document], llm: LLMProvider) -> SkillDraft`.
- `Exporter.export(draft: SkillDraft, out_dir: Path) -> list[Path]`.

## 8. End-to-end data flow (`aptitude create`)

1. **Ingest** — For each `--input`, detect type (or honor explicit `--type`), dispatch
   to the matching adapter → `Document`. Web/GitHub fetches are cached on disk keyed by
   URL / commit hash so re-runs are cheap (`--no-cache` bypasses).
2. **Process** — Count tokens across all Documents. If the combined corpus fits the
   provider's context budget (minus a synthesis reserve), pass it through unchanged.
   Otherwise **chunk → map-reduce summarize**: summarize each chunk (preserving
   provenance), then reduce to a distilled corpus that fits the budget. This is the key
   move for large PDFs and repos.
3. **Synthesize** — `template_synth` runs a short sequence of provider calls guided by
   the user's prompt: (a) derive `name` + `description`; (b) draft `body`; (c) extract
   supporting material into `references`. Produces a `SkillDraft`.
4. **Validate** — check name/description/frontmatter constraints; collect warnings.
5. **Export** — for each requested `--format`, run its exporter against the same
   `SkillDraft`, writing into `out/<skill-name>/`. The packager (`zip`) runs last if
   requested.

`--dry-run` stops after step 2 and prints the distilled corpus plus the planned skill
outline, so users can sanity-check direction and cost before paying for full synthesis.

## 9. Provider layer

Every provider implements the same `LLMProvider` ABC, so the synthesizer is
provider-blind.

| Provider | Backed by | Auth (env var) | Notes |
|---|---|---|---|
| `claude` | Anthropic Messages API | `ANTHROPIC_API_KEY` | Default when key present; confirm current model IDs against the `claude-api` skill at build time |
| `gemini` | Google Generative AI API | `GEMINI_API_KEY` | |
| `nvidia` | NVIDIA NIM (OpenAI-compatible) | `NVIDIA_API_KEY` | OpenAI-style client against NIM base URL |
| `ollama` | Local Ollama server | none | Default when no keys are set; fully offline |
| `openai` | OpenAI + any OpenAI-compatible base URL | `OPENAI_API_KEY` | Generic adapter for "other popular options" via `--base-url` |

Because NVIDIA, OpenAI, LM Studio, vLLM, and others speak the OpenAI wire format, a
single `OpenAICompatibleProvider` base class covers most of them — a new provider is
often just a base URL + a default model. Each provider declares its `context_window`
and a `count_tokens()` (exact where the SDK supports it; `tiktoken`/heuristic fallback
otherwise) so the Process stage sizes chunks correctly. Provider and model are
selectable via `--provider` / `--model`, with per-provider default models in config.

## 10. Exporter layer

Each exporter consumes the same `SkillDraft`:

- **`claude-skill`** → `out/<name>/SKILL.md` (YAML frontmatter `name` + `description`,
  body as markdown) plus `references/*.md` and `scripts/*`, matching Anthropic's Agent
  Skills layout. Canonical target.
- **`generic-prompt`** → a single portable `<name>.md` (plus a `.json` variant): a
  self-contained system prompt with instructions + distilled knowledge inlined, for any
  GenAI app.
- **`local-llm`** → forms tuned for local runtimes: an Ollama `Modelfile` with the skill
  as the `SYSTEM` prompt, plus a plain `system.txt` for LM Studio / text-gen-webui.
- **`mcp-manifest`** → `mcp.json` describing any `tools`/`scripts` the skill references,
  for function-calling / MCP wiring. Emitted only when the draft has tools.
- **`packager` (`zip`)** → bundles chosen output(s) into `<name>.zip`; can also emit a
  minimal Claude Code **plugin** structure for drop-in install.

`--format` accepts a comma-separated list (default `claude-skill`); `all` emits every
applicable format.

## 11. Extension points

- **New ingestion adapter:** implement `IngestionAdapter`, register it. (Future: docx,
  Notion, YouTube transcript, etc.)
- **New provider:** subclass `LLMProvider` (or `OpenAICompatibleProvider`), register it.
- **New exporter:** implement `Exporter`, register it.
- **V2 agentic synthesizer:** implement the `Synthesizer` ABC with an agent loop
  (tools: `read_artifact`, `summarize`, `write_file`) and register it as, e.g.,
  `--synth agentic`. Inputs/outputs are identical to `template_synth`, so no pipeline
  change is needed.
  **Implemented (V2).** `aptitude/synthesize/agentic.py` registers `AgenticSynthesizer`
  as `"agentic"`. It runs a ReAct-style loop (`chat()` + tools) against a `Toolbox`
  exposing `read_artifact`/`search`/`summarize`/`finish`, forces one self-critique pass
  before accepting `finish`, and falls back to `TemplateSynthesizer` if the agent
  doesn't converge within `max_iterations`. Selected via `aptitude create --synth
  agentic [--max-iterations N]`; wired through `RunConfig.synth`/`max_iterations` in
  `aptitude/pipeline.py` and `aptitude/cli.py`.

## 12. CLI surface (Typer)

```bash
aptitude create \
  --prompt "..."            # or @file.txt to read a long prompt from disk
  --input <path|url>        # repeatable; mixes types freely
  [--type auto]             # override auto-detection for the preceding --input
  [--provider NAME] [--model NAME]
  [--format claude-skill,generic-prompt]   # comma list; 'all' for everything
  [--out ./out]
  [--max-tokens-budget N] [--dry-run] [--no-cache] [-v]

aptitude providers          # list providers, show which have creds / are reachable
aptitude formats            # list exporters
aptitude validate <dir>     # validate an existing SKILL.md package
aptitude init               # write a starter aptitude.toml config
```

## 13. Configuration

Layered precedence: **CLI flag > env var > `aptitude.toml` > built-in default**
(`config.py`). The TOML holds default provider/model, per-provider base URLs, token
budgets, and cache location. **API keys come only from env vars** — never written to
the config file. `aptitude providers` prints the resolved selection so users can debug
"why did it pick Ollama?".

## 14. Error handling

Typed hierarchy: `AptitudeError` → `IngestionError`, `ProviderError`, `SynthesisError`,
`ExportError`, `ConfigError`.

- One bad `--input` does not kill the run: Aptitude reports it, skips it, and continues
  with the rest. If *all* inputs fail, the run fails.
- Provider calls use bounded retries with backoff on transient/rate-limit errors;
  auth/quota errors fail fast with an actionable message.
- Every error names the stage, the source/provider, and the fix.
- Exit codes: `0` ok, `1` partial (some inputs skipped), `2` fatal.

## 15. Testing strategy (TDD)

- **Unit:** each ingestion adapter against small fixtures (tiny PDF/EPUB, saved HTML
  page, fixture repo); chunker/summarizer driven by a **fake deterministic LLM provider**
  (no network); each exporter asserting exact file structure and frontmatter; the
  validator.
- **Integration:** full pipeline with the fake provider, end-to-end (prompt + fixtures →
  validated skill package), covering multi-format output and the partial-failure path.
- **Contract tests:** a shared suite every `LLMProvider` and every `Exporter` must pass,
  so new plugins are correct by construction.
- Live provider calls sit behind an opt-in marker and never run in the default suite.

## 16. Open questions

None blocking. Model-ID specifics for the `claude` provider will be confirmed against
the `claude-api` skill during implementation.
