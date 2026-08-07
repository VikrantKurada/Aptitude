# What It Doesn't Do Yet

These are places where the v1 design spec promised something the code does not do, listed here so you don't have to find them by being surprised. Each section names the gap, the file and line backing the claim, and what it costs you in practice.

## No caching

`aptitude/config.py:10` declares a `cache` default (`.aptitude-cache`) in the resolved configuration, but no file in `aptitude/` reads that key back out — a repo-wide search for `cache` turns up only that one declaration. `aptitude/ingest/github.py:16-27` clones fresh into a new temp directory on every call (`git clone --depth 1`, no check for a prior clone), and `aptitude/ingest/web.py:8-12` issues an unconditional `httpx.get` on every ingest. In practice: re-running `aptitude create` against the same GitHub repo or URL refetches or re-clones it every time. That's slow, and for hosts with anonymous rate limits (GitHub's clone/API limits in particular), running the same command a few times in a row can start failing outright.

## Token counting is a heuristic

`aptitude/process/tokens.py:2` is `return max(1, len(text) // 4)` — a fixed 4-characters-per-token estimate, used everywhere token counts matter: sizing the corpus against `--budget` in `aptitude/process/summarizer.py:20`, and deciding whether the reduced summary still needs a further condensing pass (`summarizer.py:25`). That ratio holds reasonably well for English prose and is wrong for source code (denser, more punctuation-heavy) and CJK text (fewer characters per token than Latin scripts, in the opposite direction of code). The practical effect: `--budget` is an approximation exactly in the cases where getting the budget right matters most — a code-heavy GitHub repo or a non-English document can silently blow past your intended budget, or trigger a summarization pass that a real tokenizer would have judged unnecessary.

## `context_window` is declared but unused

Every provider sets a `context_window` attribute at construction — `aptitude/llm/claude.py:53` (200000), `aptitude/llm/gemini.py:50` (1000000), `aptitude/llm/ollama.py:24` (8000), `aptitude/llm/openai.py:27` (default 8000), and the base default in `aptitude/llm/base.py:21` (8000). Nothing else in the codebase reads `context_window` back — it is set once and never consulted. `--budget` defaults to a flat `6000` tokens for every run regardless of provider (`aptitude/cli.py:32`, `aptitude/pipeline.py:20`), and nothing scales that default against the chosen provider's window. Cost: Gemini advertises a million-token context window and gets sized against the same 6000-token default as everything else. A large-context provider currently buys you nothing unless you remember to raise `--budget` yourself.

## No retries

Provider calls fail on the first error, once. `aptitude/llm/ollama.py:27-31` wraps its HTTP call in a `try/except` that converts any exception straight into a `ProviderError` — no retry, no backoff. `aptitude/llm/openai.py:32-38` doesn't even wrap the request in a `try/except`; a transient network error propagates as a raw `httpx` exception. The same single-attempt pattern holds for ingestion (`aptitude/ingest/web.py:8-12`, `aptitude/ingest/github.py:20-26`). Because synthesis (the LLM calls) always runs after ingestion completes, the cost lands late: one transient 503 from your provider ends the run after ingestion — cloning a repo, fetching a page, chunking and possibly summarizing the corpus — has already happened and has to be redone from scratch on retry.

## `scripts` and `tools` are never populated

`SkillDraft` (`aptitude/models.py:48-49`) has `scripts` and `tools` fields, but neither synthesizer fills them in: `template`'s `SkillDraft(...)` call sets `name`, `description`, `body`, `references`, and `provenance`, and stops there (`aptitude/synthesize/template_synth.py:25-28`), and `agentic`'s sets the same five (`aptitude/synthesize/agentic.py:49-54`) — its own tools (`list_sources`, `read_source`, `add_reference`, `finish`, defined in `aptitude/synthesize/agent_tools.py`) are for exploring source material during synthesis, not for populating the resulting skill's `tools` list. Two consequences follow directly: `aptitude/export/mcp_manifest.py:9` — `if not draft.tools: return []` — means the `mcp-manifest` format never writes a file, not even one with an empty tool list (see [anatomy](product/anatomy.md)); and no generated skill ever ships an executable script, since `ClaudeSkillExporter`'s loop over `[*draft.references, *draft.scripts]` (`aptitude/export/claude_skill.py:23`) has nothing in `draft.scripts` to write. Both formats/fields work correctly — there is just nothing yet that puts data into them.

## `--base-url` is TOML-only

`create`'s CLI options (`aptitude/cli.py:25-36`) have no `--base-url` flag, and `resolve_config`'s environment-variable mapping (`aptitude/config.py:23-24`) only covers `provider`, `model`, `format`, and `synth` — `base_url` isn't in it either. The only place a `base_url` config value is consumed is inside each provider's `build()` classmethod (`aptitude/llm/openai.py:65,74`, `aptitude/llm/ollama.py:58`), and the only way that value gets into the resolved config is via `aptitude.toml` (`config.py:21-22` merges TOML keys directly, with no CLI or env equivalent). In practice: pointing Aptitude at LM Studio, vLLM, or any other OpenAI-compatible endpoint works, but only by writing an `aptitude.toml` file in the working directory — there's no way to do it with a flag or environment variable for a one-off run or inside a CI job that shouldn't drop a config file.

## `max_tokens_budget` is dead config

`aptitude/config.py:10` declares `"max_tokens_budget": None` in `DEFAULTS`, sitting right alongside real, functioning settings like `format` and `synth` — so it reads like a working knob you can set in `aptitude.toml`. A repo-wide search for `max_tokens_budget` turns up exactly that one line and nothing else; no code path ever reads the resolved value back out to affect a run. The only thing that actually controls how much text gets synthesized from is the unrelated `--budget` CLI flag (`aptitude/cli.py:32`, feeding `RunConfig.budget` in `aptitude/pipeline.py:20`). Cost: if you set `max_tokens_budget` in `aptitude.toml` expecting it to cap anything, it will silently do nothing — use `--budget` instead.

## `provenance` is never written to disk

`SkillDraft.provenance` (`aptitude/models.py:50`) is filled on every run — both synthesizers set it to `[d.source.raw for d in docs]` (`aptitude/synthesize/template_synth.py:28`, `aptitude/synthesize/agentic.py:54`), and `agentic` appends `(agentic did not converge → template fallback)` to it when the agent loop runs out of iterations and the template synthesizer takes over (`aptitude/synthesize/agentic.py:26`). No exporter reads it back out: `grep -rn provenance aptitude/export/` returns nothing. `ClaudeSkillExporter` writes the name and description frontmatter, the body, then every entry in `draft.references` and `draft.scripts`, and stops (`aptitude/export/claude_skill.py:18-27`); the other four exporters build their output from the same three fields. In practice: which sources went into a skill, and whether `--synth agentic` actually ran the agent or silently fell back to `template`, are both recorded and neither is reported. Call the library and `draft.provenance` tells you. Run the CLI and the output directory looks the same either way — same `SKILL.md`, same exit code 0 — so a provider whose tool-calling quietly stops working produces runs you cannot distinguish from working ones.

For which of these are planned, and for roughly when, see [the roadmap](product/roadmap.md).

[← Back to the documentation index](index.md)
