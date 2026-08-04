# Aptitude

**Generate AI skills from artifacts.**

Aptitude distills documents, codebases, and web content into structured skills for use with Claude or other LLM providers. It ingests multiple file types (PDFs, EPUBs, GitHub repos, web pages), synthesizes them with an LLM, and exports to multiple formats ready for agent systems.

## Installation

```bash
pip install -e ".[dev]"
```

This installs Aptitude in editable mode with development dependencies (pytest for testing).

## Providers

Aptitude supports five LLM providers. Select one via `--provider` (CLI), `APTITUDE_PROVIDER` (env), or `provider` in `aptitude.toml`.

| Provider | API Key Environment Variable | Notes |
|----------|------------------------------|-------|
| `claude` | `ANTHROPIC_API_KEY` | Anthropic's Claude family |
| `gemini` | `GEMINI_API_KEY` | Google's Gemini |
| `nvidia` | `NVIDIA_API_KEY` | NVIDIA's NIM platform (OpenAI-compatible) |
| `ollama` | None | Local model via Ollama, requires no API key |
| `openai` | `OPENAI_API_KEY` | OpenAI's GPT models |

If no provider is specified and `ANTHROPIC_API_KEY` is set, defaults to `claude`; otherwise defaults to `ollama`.

## Output Formats

Aptitude can export to multiple formats. Specify via `--format` (default: `claude-skill`), or request all formats with `--format all`.

| Format | Description |
|--------|-------------|
| `claude-skill` | SKILL.md + supporting files for use in Claude Canvas or Skill Builder |
| `generic-prompt` | Single markdown document ready to paste into any LLM chat |
| `local-llm` | Markdown optimized for local models (compact headers, adjusted for smaller context windows) |
| `mcp-manifest` | MCP resource manifest (JSON) for integration with Model Context Protocol servers |
| `zip` | All formats bundled into a single zip archive |

## Configuration

Aptitude resolves configuration with the following precedence (highest to lowest):

1. **CLI options** (e.g., `--provider claude`, `--model gpt-4o-mini`)
2. **Environment variables** (e.g., `APTITUDE_PROVIDER=claude`, `APTITUDE_MODEL=gpt-4o`)
3. **`aptitude.toml`** (file in current directory)
4. **Defaults** (provider: claude if `ANTHROPIC_API_KEY` else ollama; format: claude-skill)

Example `aptitude.toml`:
```toml
provider = "ollama"
model = "llama3.1"
format = "claude-skill"
```

## Commands

### `create` — Generate a skill from artifacts

```bash
aptitude create --prompt "PROMPT" --input FILE [--input FILE ...] [OPTIONS]
```

**Options:**
- `--prompt, -p` — Skill description (required)
- `--input, -i` — Source artifact: file path, GitHub URL, or web URL (repeatable)
- `--provider` — LLM provider name (overrides env/config)
- `--model` — Model ID (overrides env/config)
- `--format` — Export format(s): `claude-skill`, `generic-prompt`, `local-llm`, `mcp-manifest`, `zip`, or `all` (default: `claude-skill`)
- `--out` — Output directory (default: `./out`)
- `--budget` — Maximum tokens to synthesize (default: 6000)
- `--dry-run` — Parse and ingest without LLM synthesis; preview the corpus
- `-v` — Verbose output

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

Output: `./out/` containing a `claude-skill/` directory with SKILL.md and supporting files.

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

Output: `./out/` containing subdirectories for each format (claude-skill/, generic-prompt/, etc.) plus a zip file.

### 3. Preview the Corpus Without Synthesis

Parse and ingest sources without calling an LLM—useful to preview what will be synthesized:

```bash
aptitude create \
  --prompt "..." \
  --input big-book.epub \
  --dry-run
```

Output: Prints the extracted and chunked corpus (first 2000 characters) to stdout. No LLM calls are made; no output files are written.

## See Also

- `aptitude --help` — Show all commands and global options
- `aptitude COMMAND --help` — Show help for a specific command
