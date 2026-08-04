# Aptitude

[![tests](https://github.com/VikrantKurada/Aptitude/actions/workflows/tests.yml/badge.svg)](https://github.com/VikrantKurada/Aptitude/actions/workflows/tests.yml)

**Generate AI skills from artifacts.**

Aptitude distills documents, codebases, and web content into structured skills for use with Claude or other LLM providers. It ingests multiple file types (PDFs, EPUBs, GitHub repos, web pages), synthesizes them with an LLM, and exports to multiple formats ready for agent systems.

## Installation

```bash
pip install -e ".[dev]"
```

This installs Aptitude in editable mode with development dependencies (pytest for testing).

## Quick start

The launcher scripts set up a local virtual environment on first run, install Aptitude into it, and then run the CLI — no manual setup needed. Arguments are forwarded straight to `aptitude`.

```bash
# Linux / macOS
./start.sh providers
./start.sh create -p "Build a GDPR privacy-policy skill" -i law.pdf --provider ollama
```

```powershell
# Windows (PowerShell)
.\start.ps1 providers
.\start.ps1 create -p "Build a GDPR privacy-policy skill" -i law.pdf --provider ollama
```

Once installed (via the launcher or `pip install -e .`), you can also invoke the CLI directly as `aptitude ...` or `python -m aptitude ...`.

## Providers

Aptitude supports five LLM providers. Select one via `--provider` (CLI), `APTITUDE_PROVIDER` (env), or `provider` in `aptitude.toml`.

| Provider | API Key Environment Variable | Default Model |
|----------|------------------------------|---|
| `claude` | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| `nvidia` | `NVIDIA_API_KEY` | `meta/llama-3.1-70b-instruct` |
| `ollama` | None (local) | `llama3.1` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |

If no provider is specified and `ANTHROPIC_API_KEY` is set, defaults to `claude`; otherwise defaults to `ollama`.

## Output Formats

Aptitude can export to multiple formats. Specify via `--format` (default: `claude-skill`), or request all formats with `--format all`.

| Format | Description |
|--------|-------------|
| `claude-skill` | SKILL.md + supporting files for use in Claude Canvas or Skill Builder |
| `generic-prompt` | Single markdown document ready to paste into any LLM chat |
| `local-llm` | Markdown optimized for local models (compact headers, adjusted for smaller context windows) |
| `mcp-manifest` | MCP resource manifest (JSON) for integration with Model Context Protocol servers |
| `zip` | Bundles the generated skill directory into a single `.zip`. Combine with `--format all` (or list the formats you want) to include every format; used alone it bundles just the `claude-skill` files. |

## Synthesizers

Aptitude ships two synthesis strategies, selected via `--synth`:

| Synth | Description |
|-------|-------------|
| `template` | Default. A fixed, 3-call pipeline (outline → body → refine) against the distilled corpus. Fast, deterministic, and works with every provider — including ones without tool-calling support. |
| `agentic` | The agentic synthesizer runs an LLM agent loop with tools — `list_sources` and `read_source` to explore the ingested material selectively, `add_reference` to save distilled reference files, a forced self-critique pass, then `finish` — falling back to the template synthesizer if it doesn't converge within `--max-iterations`. Requires a provider/model capable of reliable tool use. |

Select the agentic synthesizer with `--synth agentic`, and tune its iteration budget with `--max-iterations` (default `12`, the max number of agent loop turns before giving up).

**Fallback behavior:** if the agent doesn't converge on a `finish` call within `--max-iterations` (e.g. the model never emits a valid tool call, or the provider doesn't support tools), `agentic` automatically falls back to the `template` synthesizer so the run still succeeds — this is the intended, robust default. The generated skill's provenance notes when the fallback path was used.

```bash
aptitude create -p "Build a skill for our API" -i docs.pdf --provider claude --synth agentic --max-iterations 20
```

## Configuration

Aptitude resolves **provider, model, output format, and synthesizer** with the following precedence (highest to lowest):

1. **CLI options** (e.g., `--provider claude`, `--model gpt-4o-mini`, `--format zip`, `--synth agentic`)
2. **Environment variables** (`APTITUDE_PROVIDER`, `APTITUDE_MODEL`, `APTITUDE_FORMAT`, `APTITUDE_SYNTH`)
3. **`aptitude.toml`** (file in current directory: `provider`, `model`, `format`, `synth`)
4. **Defaults** (provider: claude if `ANTHROPIC_API_KEY` else ollama; format: `claude-skill`; synth: `template`)

Example `aptitude.toml`:
```toml
provider = "ollama"
model = "llama3.1"
format = "claude-skill"
synth = "agentic"
```

## Commands

### `create` — Generate a skill from artifacts

```bash
aptitude create --prompt "PROMPT" --input FILE [--input FILE ...] [OPTIONS]
```

**Options:**
- `--prompt, -p` — Skill description (required). Use `@path/to/file.txt` to read a long prompt from disk.
- `--input, -i` — Source artifact: file path, GitHub URL, or web URL (repeatable).
- `--type` — Force the artifact type for **all** `-i` inputs in this run: `auto`, `pdf`, `epub`, `web`, or `github` (default: `auto`, which detects each input's type independently). Use separate runs if different inputs need different forced types.
- `--provider` — LLM provider name (overrides env/config).
- `--model` — Model ID (overrides env/config).
- `--format` — Export format(s): `claude-skill`, `generic-prompt`, `local-llm`, `mcp-manifest`, `zip`, or `all`. Comma-separated for multiple, e.g., `--format claude-skill,zip`. Overrides `APTITUDE_FORMAT` / `aptitude.toml`; ultimate default is `claude-skill`.
- `--out` — Output directory (default: `./out`). All formats write to `out/<skill-name>/`.
- `--budget` — Maximum tokens to synthesize (default: 6000).
- `--synth` — Synthesis strategy: `template` (default) or `agentic`. Overrides `APTITUDE_SYNTH` / `aptitude.toml`; ultimate default is `template`. See [Synthesizers](#synthesizers).
- `--max-iterations` — Max agent loop turns for `--synth agentic` before falling back to `template` (default: 12). Ignored by `template`.
- `--dry-run` — Ingest and process the artifacts and print the distilled corpus and planned skill outline, then stop before synthesis. Note: for inputs larger than `--budget`, the distillation step itself summarizes via the selected provider (making LLM calls), so it is not entirely free. Use `--provider ollama` (local) for a zero-cost preview.
- `-v` — Verbose output.

### `providers` — List available providers and their configuration status

```bash
aptitude providers
```

Shows each provider name and whether it is "ready" (API key configured or local) or "no key".

### `formats` — List all available export formats

```bash
aptitude formats
```

### `validate` — Validate a skill directory

```bash
aptitude validate PATH
```

Checks that a skill directory follows the expected structure. Exits with code 0 if valid, 2 if invalid.

### `init` — Initialize aptitude.toml in the current directory

```bash
aptitude init
```

Creates `aptitude.toml` with sensible defaults (ollama + llama3.1 + claude-skill format).

## Examples

### 1. PDF → Claude Skill via Ollama

Generate a structured skill from a PDF document using a local Ollama model:

```bash
aptitude create \
  --prompt "Skill for drafting GDPR privacy policies" \
  --input privacy-law.pdf \
  --provider ollama
```

Output: `./out/<skill-name>/` containing SKILL.md and supporting files in a flat structure.

### 2. Repository + Web Page → All Formats via Claude

Combine source code and documentation into multiple export formats using Claude:

```bash
aptitude create \
  --prompt "Skill for using our API" \
  --input github.com/acme/sdk \
  --input https://docs.acme.dev \
  --provider claude \
  --format all
```

Output: `./out/<skill-name>/` containing all format files in a flat structure (SKILL.md, `<skill-name>.md`, `<skill-name>.json`, Modelfile, system.txt, mcp.json, and reference materials), plus `./out/<skill-name>.zip` bundling the entire skill directory.

### 3. Preview the Corpus Without Synthesis

Preview the distilled corpus before committing to a full skill synthesis, using a zero-cost local provider:

```bash
aptitude create \
  --prompt "Skill for analyzing quarterly earnings reports" \
  --input big-book.epub \
  --provider ollama \
  --dry-run
```

Output: Prints the extracted and processed corpus (first 2000 characters) to stdout, then exits without writing files or calling the LLM synthesis step. Use `--provider ollama` (or another local provider) to avoid API charges. Note: if the corpus exceeds `--budget` tokens, the distillation step will still call the provider to summarize chunks.

## See Also

- `aptitude --help` — Show all commands and global options
- `aptitude COMMAND --help` — Show help for a specific command
