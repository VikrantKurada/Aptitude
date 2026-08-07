# What Aptitude Does

Aptitude turns a prompt plus a set of artifacts (PDFs, EPUBs, web pages, GitHub repos) into a reusable skill. Every run follows the same fixed pipeline: `Ingest → Process → Synthesize → Export` — see [the architecture page](../engineering/architecture.md) for how each stage works internally.

## Inputs

Aptitude ingests four artifact types, each handled by its own adapter:

| Type | Detected when | What gets extracted |
|------|----------------|----------------------|
| `pdf` | Path/URL ends in `.pdf` | Text per page (via `pypdf`); one section per page |
| `epub` | Path/URL ends in `.epub` | Text per chapter/document item (via `ebooklib` + BeautifulSoup); the navigation/TOC document is skipped |
| `web` | An `http://`/`https://` URL whose host is not `github.com` (or a `*.github.com` subdomain) | Page title (`<title>`, falling back to `<h1>`); body text with `script`, `style`, `nav`, `footer`, `header`, and `aside` tags stripped, preferring `<main>`, then `<article>`, then `<body>` |
| `github` | An `http(s)://github.com/...` URL, or a bare `owner/repo` shorthand (owner segment has no dot, so domain-like strings such as `example.com/page` aren't misdetected) | A shallow clone (`git clone --depth 1`); all `README*` files, every `docs/**/*.md` file (truncated to 4000 characters each), and extracted function/class signatures from source files with extensions `.py`, `.js`, `.ts`, `.tsx`, `.go`, `.rs`, `.java` |

Detection checks run in this order: file extension first (so a URL ending in `.pdf` is treated as `pdf`, not `web`), then the GitHub-host check, then the bare `owner/repo` shorthand.

`--type auto` (the default) runs this detection independently for each `-i` input. Passing an explicit `--type` (e.g. `--type pdf`) forces that type for **every** `-i` input in the run, not just the one it's next to on the command line — use separate `aptitude create` invocations if different inputs need different forced types.

## Providers

Aptitude supports five LLM providers, selected via `--provider` (CLI), `APTITUDE_PROVIDER` (env), or `provider` in `aptitude.toml`.

| Provider | API key environment variable | Default model |
|----------|-------------------------------|----------------|
| `claude` | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| `nvidia` | `NVIDIA_API_KEY` | `meta/llama-3.1-70b-instruct` |
| `ollama` | None (local) | `llama3.1` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |

If no provider is resolved from CLI, env, or `aptitude.toml`, Aptitude defaults to `claude` when `ANTHROPIC_API_KEY` is set in the environment, and to `ollama` otherwise.

`nvidia` and `openai` are two registrations of the same OpenAI-compatible client implementation (`OpenAICompatibleProvider`) — they differ only in default model, API key variable, and default base URL. That base URL (`base_url`) can be overridden per run, but only as a key in `aptitude.toml`; there is no `--base-url` CLI flag and no environment variable for it. See [the limitations page](../limitations.md) for other configuration-surface gaps.

## Output Formats

Aptitude exports to five formats, selected via `--format` (default: `claude-skill`), or `--format all` for every format at once. Multiple formats can be comma-separated (`--format claude-skill,zip`).

| Format | Description |
|--------|-------------|
| `claude-skill` | `SKILL.md` (with YAML frontmatter) plus reference/script files, for use in Claude Canvas or Skill Builder |
| `generic-prompt` | A single markdown document and a matching JSON file, ready to paste into any LLM chat |
| `local-llm` | An Ollama `Modelfile` (skill content as the `SYSTEM` prompt, with `FROM` hardcoded to `llama3.1` regardless of which model you actually used) plus a plain `system.txt` for runtimes like LM Studio — the same prompt content as `generic-prompt`, just packaged differently; not smaller and not context-window-adjusted |
| `mcp-manifest` | Nothing, today: the exporter returns early while `draft.tools` is empty, and nothing populates it |
| `zip` | An archive of everything already in `out/<skill-name>/`, so under `--format all` it picks up the other formats' files too |

`mcp-manifest` currently ships no content: `SkillDraft` has a `tools` field for MCP tool specs, but neither the `template` synthesizer nor the `agentic` synthesizer populates it — the agentic synthesizer's own tools (`list_sources`, `read_source`, `add_reference`, `finish`) are for exploring source material during synthesis, not for the resulting skill. Because `draft.tools` is always empty, the exporter returns without writing any file at all (not even an `mcp.json` with an empty tools array). See [the limitations page](../limitations.md) for tracking status.

## Synthesizers

Aptitude ships two synthesis strategies, selected via `--synth`:

| Synth | Description |
|-------|-------------|
| `template` (default) | A fixed, 3-call pipeline (name/description → body → reference material) against the distilled corpus. Same 3 calls in the same order every run, no branching and no agent loop — unlike `agentic`, the call sequence never varies — and it works with every provider, including ones without tool-calling support. Nothing in the pipeline pins a temperature or seed, so model output for a given call can still vary between runs. |
| `agentic` | Runs an LLM agent loop with tools: `list_sources` and `read_source` to explore the ingested material selectively, `add_reference` to save distilled reference files, then `finish`. Requires a provider/model capable of reliable tool use. |

Select the agentic synthesizer with `--synth agentic`, and tune its iteration budget with `--max-iterations` (default `12`).

**Forced self-critique:** the first time the agent calls `finish`, Aptitude does not accept it. It sends one forced critique prompt back to the model and requires a second `finish` call before the draft is accepted. That extra round counts against `--max-iterations`.

**Fallback behavior:** if the agent doesn't reach an accepted `finish` within `--max-iterations` turns — e.g. the model never emits a valid tool call, or the provider doesn't support tools — `agentic` automatically falls back to running the `template` synthesizer's 3-call pipeline instead, so the run still succeeds. The generated draft's `provenance` list then includes the line `(agentic did not converge → template fallback)` (`aptitude/synthesize/agentic.py:26`). That line never reaches the output directory, though: no exporter writes `provenance` to disk, so a caller using Aptitude as a library can tell which path produced a draft and a CLI user cannot. See [the limitations page](../limitations.md#provenance-is-never-written-to-disk).

```bash
aptitude create -p "Build a skill for our API" -i docs.pdf --provider claude --synth agentic --max-iterations 20
```

## Cost and Latency

- `template` makes a fixed 3 provider calls per run (name/description, body, reference material), regardless of corpus size, beyond whatever calls distillation itself makes (see `--dry-run` below).
- `agentic`'s agent loop makes at most `--max-iterations` provider calls (default 12) — one call per iteration, hard-capped by the loop bound. The forced self-critique consumes one of those iterations like any other turn; it is not an extra call on top (see [Synthesizers](#synthesizers)). If the budget runs out without an accepted `finish` — including when the critique lands on the final iteration, leaving no iteration left for the second `finish` — the run falls back to `template` and pays its 3 calls on top of the exhausted budget. Those 3 are not the whole bill: `template` starts by calling `distill()`, which makes one provider call per chunk whenever the corpus exceeds `--budget` (`aptitude/process/summarizer.py:22-23`), plus one more if the joined summaries still overflow (`summarizer.py:25-29`). So the worst case is `max_iterations + 3 + one call per chunk`, not `max_iterations + 1`. Chunks are capped at `max(500, budget // 4)` (`summarizer.py:22`), so at the default `--budget 6000` they are 1500 tokens each: a 50,000-token corpus is about 34 chunks, and 12 iterations that go nowhere on it cost roughly 12 + 34 + 3 = 49 provider calls, not 15.
- `--dry-run` stops after ingestion and distillation, before synthesis, and prints the first 2000 characters of the distilled corpus. It is not free: if the combined corpus exceeds `--budget` tokens, the distillation step summarizes the overflow through the selected provider, which makes LLM calls.
- Use `--provider ollama` for a zero-cost, local preview — this applies to normal runs and to `--dry-run` runs whose corpus exceeds `--budget`.

## Configuration

Aptitude resolves **provider, model, output format, and synthesizer** with the following precedence (highest to lowest):

1. **CLI options** (e.g., `--provider claude`, `--model gpt-4o-mini`, `--format zip`, `--synth agentic`)
2. **Environment variables** (`APTITUDE_PROVIDER`, `APTITUDE_MODEL`, `APTITUDE_FORMAT`, `APTITUDE_SYNTH`)
3. **`aptitude.toml`** (file in current directory: `provider`, `model`, `format`, `synth`)
4. **Defaults** (provider: `claude` if `ANTHROPIC_API_KEY` else `ollama`; format: `claude-skill`; synth: `template`)

Every other `create` option (`--input`/`-i`, `--type`, `--out`, `--budget`, `--max-iterations`, `--dry-run`, `-v`) is CLI-only, with no environment-variable or `aptitude.toml` layer, and no config-file default beyond the flag's own default. `base_url` is the exception in the other direction: it can be set only in `aptitude.toml` (see [Providers](#providers)), with no CLI flag or environment variable of its own.

Example `aptitude.toml`:
```toml
provider = "ollama"
model = "llama3.1"
format = "claude-skill"
synth = "agentic"
```

## Commands

### `create` — generate a skill from artifacts

```bash
aptitude create --prompt "PROMPT" --input FILE [--input FILE ...] [OPTIONS]
```

| Option | Default | Notes |
|--------|---------|-------|
| `--prompt, -p` | required | Skill description. Use `@path/to/file.txt` to read a long prompt from disk. |
| `--input, -i` | none | Source artifact: file path, GitHub URL, or web URL. Repeatable. |
| `--type` | `auto` | Force the artifact type (`auto`, `pdf`, `epub`, `web`, `github`) for **all** `-i` inputs in this run. See [Inputs](#inputs). |
| `--provider` | resolved per [Configuration](#configuration) | LLM provider name. |
| `--model` | provider's default model | Model ID. |
| `--format` | resolved per [Configuration](#configuration), ultimately `claude-skill` | Export format(s): `claude-skill`, `generic-prompt`, `local-llm`, `mcp-manifest`, `zip`, or `all`. Comma-separated for multiple. |
| `--out` | `./out` | Output directory. The skill directory is `out/<skill-name>/`; the `zip` archive lands beside it at `out/<skill-name>.zip`. |
| `--budget` | `6000` | Maximum tokens to synthesize from. |
| `--synth` | resolved per [Configuration](#configuration), ultimately `template` | Synthesis strategy: `template` or `agentic`. See [Synthesizers](#synthesizers). |
| `--max-iterations` | `12` | Max agent loop turns for `--synth agentic` before falling back to `template`. Ignored by `template`. |
| `--dry-run` | off | Ingest and process the artifacts, print the distilled corpus, then stop before synthesis. See [Cost and Latency](#cost-and-latency) — this is not always free. |
| `-v` | off | Verbose output (no `--verbose` long form). |

### `providers` — list available providers and their configuration status

```bash
aptitude providers
```

Prints each provider name and whether it is `ready` (API key configured, or `ollama`/`fake` which need none) or `no key`.

### `formats` — list all available export formats

```bash
aptitude formats
```

### `validate` — validate a skill directory

```bash
aptitude validate PATH
```

Checks that `PATH` contains a `SKILL.md` with valid YAML frontmatter (a name matching `^[a-z0-9]+(-[a-z0-9]+)*$`, no longer than 64 characters, and a non-empty description no longer than 1024 characters). Exits with code 0 if valid (printing `valid`, plus any warnings such as a very short body), or 2 if invalid.

### `init` — initialize `aptitude.toml` in the current directory

```bash
aptitude init
```

Writes an `aptitude.toml` with `provider = "ollama"`, `model = "llama3.1"`, `format = "claude-skill"`. Exits with code 1 without writing anything if `aptitude.toml` already exists.

[← Back to the documentation index](../index.md)
