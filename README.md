# Aptitude

[![tests](https://github.com/VikrantKurada/Aptitude/actions/workflows/tests.yml/badge.svg)](https://github.com/VikrantKurada/Aptitude/actions/workflows/tests.yml)

**Generate AI skills from artifacts.**

Aptitude reads PDFs, EPUBs, web pages, and GitHub repositories, and turns them — plus a one-line prompt — into a reusable skill: a `SKILL.md` with its supporting files, or the same content repackaged for another runtime. The artifacts say what is true, the prompt says what is relevant.

## Install

```bash
pip install -e ".[dev]"
```

That installs the CLI in editable mode with the test dependencies; afterwards you can run `aptitude ...` or `python -m aptitude ...`. To skip the setup, use the launchers instead — `start.sh` (Linux/macOS) and `start.ps1` (Windows) create a local virtual environment on first run, install Aptitude into it, and forward every argument straight to the CLI.

```bash
./start.sh providers          # Linux / macOS
.\start.ps1 providers         # Windows (PowerShell)
```

## Example

```bash
aptitude create \
  -p "Onboard a new engineer to this HTTP library: what it does, how it is laid out, and where to start reading" \
  -i psf/requests \
  --provider ollama --model mistral-small:latest
```

The model names the skill, and the directory is named after it. This is the tree that run produced:

```text
out/
└── onboard-new-engineer-to-requests-library/
    ├── SKILL.md                     # YAML frontmatter (name, description) then the body
    └── references/
        └── source-material.md       # the whole corpus distilled into one reference file
```

```bash
$ aptitude validate ./out/onboard-new-engineer-to-requests-library
valid
```

That is the default format. Every other format writes into the same flat `out/<skill-name>/` directory, and `--format all` runs each one in turn — [Anatomy of a Generated Skill](docs/product/anatomy.md) walks through a real `--format all` run file by file, including the format that writes nothing.

## Providers

| Provider | API key environment variable | Default model |
|----------|-------------------------------|----------------|
| `claude` | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| `nvidia` | `NVIDIA_API_KEY` | `meta/llama-3.1-70b-instruct` |
| `ollama` | None (local) | `llama3.1` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |

Choose one with `--provider`, `APTITUDE_PROVIDER`, or `provider` in `aptitude.toml`. With none of those set, Aptitude uses `claude` when `ANTHROPIC_API_KEY` is present and `ollama` otherwise. Full precedence rules, per-command options, and the two synthesis strategies are in [docs/product/features.md](docs/product/features.md).

## Output formats

| Format | What it writes |
|--------|----------------|
| `claude-skill` | `SKILL.md` plus reference files, for Claude Canvas or Skill Builder |
| `generic-prompt` | `<skill-name>.md` and `<skill-name>.json`, both carrying one prompt ready to paste into any chat |
| `local-llm` | An Ollama `Modelfile` and a `system.txt`, both carrying the same prompt text as `generic-prompt` |
| `mcp-manifest` | Nothing, today: the exporter returns early while `draft.tools` is empty, and nothing populates it |
| `zip` | An archive of everything already in `out/<skill-name>/`, so under `--format all` it picks up the other formats' files too |

Select with `--format` (default `claude-skill`), comma-separated for several, or `--format all` for every one. Per-format detail is in [docs/product/features.md](docs/product/features.md).

## Documentation

Start at [docs/index.md](docs/index.md), or go straight to a page:

| Page | For |
|---|---|
| [Why Aptitude Exists](docs/why.md) | Understanding the problem it solves |
| [What Aptitude Does](docs/product/features.md) | Commands, providers, formats, configuration |
| [Anatomy of a Generated Skill](docs/product/anatomy.md) | What the output actually looks like |
| [The Product Manager's View](docs/product/perspective.md) | Why it was sequenced this way |
| [Where This Goes](docs/product/roadmap.md) | What is planned, and what is not |
| [The Architect's View](docs/engineering/architecture.md) | How fifty combinations fit in 1,371 lines |
| [Key Decisions](docs/engineering/decisions.md) | What was chosen, rejected, and what would change it |
| [Adding a Provider, Format, or Adapter](docs/engineering/extending.md) | Contributing code |
| [The Art of the Possible](docs/possible.md) | Recipes and speculation |
| [What It Doesn't Do Yet](docs/limitations.md) | Known gaps, with evidence |

`aptitude --help` and `aptitude COMMAND --help` cover the same surface from the terminal.
