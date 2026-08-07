# Where This Goes

There is one rule holding this page together: nothing gets a near-term row unless it is a gap that already exists in the code. Not a feature someone wanted. A line that is missing, or a line that is wrong, with a file and a number next to it.

That rule is cheap to apply here because the gaps were written down first. [limitations.md](../limitations.md) is eight sections, each naming a file and a line, and it was written by reading the source rather than the plan. The near-term table below is that list with an intention attached to each entry. If a row here has no counterpart there, it does not belong in Near.

There are no dates. The ordering is the claim; a calendar would be a second claim, and one nobody could check.

## Near — close the gaps

None of these needs a new abstraction. Most are a handful of lines. The two that aren't are coupled to each other, and the table says so.

| Item | The gap today | Limitation |
|---|---|---|
| Disk cache for `web` and `github`, plus a `--no-cache` flag | `config.py:10` declares `"cache": ".aptitude-cache"` and no file reads it back. `ingest/github.py` shallow-clones into a fresh temp directory every run; `ingest/web.py` issues an unconditional `httpx.get`. Re-running the same command refetches everything, which is slow and eventually rate-limited. | [No caching](../limitations.md#no-caching) |
| Real token counting | `process/tokens.py:2` is `max(1, len(text) // 4)`. That estimate is wrong in one direction for source code and the other for CJK, so `--budget` is least accurate on exactly the corpora where it matters. | [Token counting is a heuristic](../limitations.md#token-counting-is-a-heuristic) |
| Default `--budget` from `provider.context_window` | All five providers declare a window and nothing consumes it; `tests/llm_contract.py:5` asserts a value no production line reads. Gemini's million-token window is sized against the same flat 6000 as an 8k local model. Cannot ship before real token counting — [The Architect's View](../engineering/architecture.md) explains why the two have to move together. | [`context_window` is declared but unused](../limitations.md#context_window-is-declared-but-unused) |
| Bounded retries with backoff | `llm/ollama.py:27-31` converts any exception straight into `ProviderError`; `llm/openai.py:32-38` does not wrap the request at all. Because synthesis runs after ingestion, one transient 503 throws away a completed clone, chunk and distill. | [No retries](../limitations.md#no-retries) |
| `--base-url` as a CLI flag and an env var | The value is already consumed by `build()` in `llm/openai.py:65,74` and `llm/ollama.py:58`. The only way to set it is `aptitude.toml`, so pointing at LM Studio or vLLM for one run means writing a file. | [`--base-url` is TOML-only](../limitations.md#--base-url-is-toml-only) |
| Delete `max_tokens_budget` | `config.py:10` declares it beside `format` and `synth`, so it reads like a working knob. It appears exactly once in the repository. Setting it does nothing. | [`max_tokens_budget` is dead config](../limitations.md#max_tokens_budget-is-dead-config) |
| Write `provenance` into the exported skill | Searching `aptitude/export/` for `provenance` returns nothing. `claude_skill.py` writes name and description frontmatter, the body, references and scripts, and nothing else, so `(agentic did not converge → template fallback)` lives on the in-memory draft and never reaches a CLI user. | [`provenance` is never written to disk](../limitations.md#provenance-is-never-written-to-disk) |

That covers seven of the eight. The remaining one — [`scripts` and `tools` are never populated](../limitations.md#scripts-and-tools-are-never-populated) — is deliberately not in the table. Filling those two fields is not a fix; it is a feature with open design questions attached, and it is in Far.

## Mid — make generated skills verifiable

The theme is one sentence: there is no way to tell whether a generated skill is any good. `validate_draft` checks that a name matches a regex and a description fits in 1024 characters (`validate/validator.py:18-28`), which is well-formedness. Nothing looks at the content.

Everything downstream of that is guesswork. The default synthesizer is `template` on an argument, not a measurement ([the product view](perspective.md)). The critique count is one because one read better than zero, which is the whole of the evidence behind [decision 7](../engineering/decisions.md). Both of those become answerable questions the moment a score exists, and stay unanswerable until it does.

| Item | What it unlocks |
|---|---|
| A scorer for a `SkillDraft` | Turns "agentic produces better skills" into a number that can be wrong. Every other row in this section waits on it. |
| Generate → score → regenerate | Makes `--max-iterations` and the number of forced critiques tunable against evidence instead of taste. |
| `search_sources` | A keyword index over the ingested `Document`s, so the agent can locate a section without spending read budget scanning for it. Named in the V2 spec's §3 as "a `search_sources` keyword-index tool (possible future addition; not in this version)". |
| `docx`, Notion and YouTube-transcript adapters | Each is one `IngestionAdapter` plus one registration, no pipeline change — see [extending.md](../engineering/extending.md). The v1 spec's §11 listed exactly these three as future adapters in its original commit, `0acfd2b`. None has been built. |

The intake row is last on purpose. Widening what goes in is the easiest work here and the least valuable while nothing measures what comes out.

## Far — skills that do things

Everything Aptitude generates today is text. `SkillDraft` has two fields for the other kind of output and neither has ever held anything.

| Item | Where it stands |
|---|---|
| Populate `draft.scripts` | The write path already exists: `ClaudeSkillExporter` loops over `[*draft.references, *draft.scripts]` (`export/claude_skill.py:23`) and finds the second list empty on every run. What is missing is a synthesizer that emits runnable helpers, and an answer to whether generated code should be written to disk unreviewed. |
| Populate `draft.tools` | `export/mcp_manifest.py:9` is `if not draft.tools: return []`, so `mcp-manifest` writes no file at all — not even an empty one. Filling `tools` turns a registered no-op into a format that produces something. |
| A `plugin` export format | One more registration under `export_registry`, emitting the directory shape a Claude Code plugin loader expects rather than one you copy into place by hand. |

That last row needs a line drawn through it. Writing a plugin bundle is an export format. *Installing* it into a running environment is not — the v1 spec's §3 lists "Automated publishing/installation into a live Claude Code environment" as a non-goal, and emitting a well-shaped directory does not quietly overturn that. If Aptitude ever reaches into a live environment, it should be because someone argued for it, not because an exporter grew.

## What is not planned

Four things from the v1 non-goals stay non-goals: a web UI, a hosted service, deep website crawling with full-source-tree analysis, and automated publishing into a live environment.

The first two are the same decision twice. Aptitude is about 1,371 lines and a `template` run against `--provider ollama` costs nothing but time and electricity; the argument in [why.md](../why.md) is that skills become disposable once the marginal cost of one is near zero. A hosted service reintroduces exactly the cost that argument removes, and a UI is a second surface to keep in step with a CLI that already changes faster than its docs.

Deep crawling is a different kind of refusal. The GitHub adapter reads `README*`, `docs/**/*.md` truncated to 4000 characters, and function and class signatures from seven file extensions (`ingest/github.py:37-55`). That is a deliberately shallow read, and it is what gives a whole repository a chance of fitting under a 6000-token budget. Crawling more is not obviously an improvement while nothing measures the output: a larger corpus, more summarization calls, and no evidence of a better skill. Which is the conclusion everywhere else on this page too. Build the scorer first.

[← Back to the documentation index](../index.md)
