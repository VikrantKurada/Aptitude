# Contributing

Aptitude is about 1,371 lines of Python behind four extension seams, and the interesting contributions add a fifth provider, a sixth format, or a new ingestion adapter without touching anything downstream. **[docs/engineering/extending.md](docs/engineering/extending.md) is the real guide** — step by step, with the code and the contract test each new implementation has to pass. This page is the setup around it.

## Setup

```bash
git clone https://github.com/VikrantKurada/Aptitude
cd Aptitude
pip install -e ".[dev]"
pytest
```

The default suite is offline — no network, no API keys. Every provider is tested against a mocked transport or an injected fake client, and `FakeProvider` drives the whole agent loop from canned strings. Tests that hit a real provider sit behind the `live` marker and are deselected by default (`pyproject.toml`).

## The shape of a change

- **Write the test first.** The suite was built that way, and the layout follows it: one test module per adapter, provider, and exporter, plus the pipeline and the docs.
- **Add, don't branch.** A new provider is one file under `aptitude/llm/` and one import line in `aptitude/llm/__init__.py`; a new format is one file under `aptitude/export/` and one import in `cli.py`. If your change adds an `if` to `pipeline.run()`, it is probably in the wrong place — see [The Architect's View](docs/engineering/architecture.md).
- **Cite the code in the docs.** Every page under `docs/` is written against the code as it stands and cites a file and a line wherever a claim needs one. `tests/test_docs.py` fails if a registered format or provider is not mentioned in the docs, so the reference cannot drift from the registries.
- **Keep it honest.** [What It Doesn't Do Yet](docs/limitations.md) lists the real gaps, each with file-and-line evidence. If your change closes one, delete the entry; if it opens one, add it.

## CI

Every push and pull request runs `pytest` across Python 3.11, 3.12, 3.13, and 3.14 ([.github/workflows/tests.yml](.github/workflows/tests.yml)). Green on all four is the bar.
