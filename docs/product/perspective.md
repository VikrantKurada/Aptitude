# The Product Manager's View

Aptitude's design spec is dated 3 August 2026. Its §3 lists what v1 would not do, and the first line is agentic synthesis. §4 says why it lost: "flexible but nondeterministic, costlier, and tool-calling support is uneven across Ollama/NVIDIA." What shipped instead was `TemplateSynthesizer` — three provider calls in a fixed order, name and description, then body, then reference material (`aptitude/synthesize/template_synth.py:18-24`).

Writing your most interesting feature down as a non-goal on day one reads like timidity. It was the plan, and there are two measurable reasons it was right.

## The boring version proved the pipeline

The agentic synthesizer arrived a day later. `git diff --stat 198d105 da7d6e6 -- aptitude/` — the last v1 commit through the last V2 commit — is twelve files, 378 insertions, 9 deletions. Not one of those twelve is under `aptitude/ingest/`, `aptitude/process/`, `aptitude/export/`, or `aptitude/validate/`. `models.py` is untouched too: the agent describes its tools with `ToolSpec`, a dataclass v1 had already defined and never used.

There were 24 test modules at `198d105`, covering four ingestion adapters, the chunker, the map-reduce summarizer, every provider, every exporter, the validator and the pipeline. So the new code only had to be an agent loop. `agentic.py` is 57 lines, `agent_tools.py` 72, `agent_prompts.py` 16, and the ReAct text fallback `tools_react.py` 46 — under two hundred lines, because everything underneath them already worked.

Reverse the order and those two hundred lines would also have had to settle what a chunk is and what an agent's output contains, while being an agent.

## The seam was reserved, and the seam held

The v1 spec's §11 promised of the future synthesizer that its "Inputs/outputs are identical to `template_synth`, so no pipeline change is needed." That clause is in the original spec commit, `0acfd2b`, not added later, and it came true. `git log -- aptitude/pipeline.py` returns two commits in total; the second added a `max_iterations` field to `RunConfig` and a four-line `try/except TypeError` around the constructor call — plumbing for a flag, not a branch for a synthesizer. `AgenticSynthesizer` announced itself with a decorator and `run()` never learned it existed.

The same §11 sentence also guessed which tools the agent would have, and got all three wrong.[^1] So the score is one for one: the architectural prediction held, the detail prediction did not survive contact. Take a spec's interfaces as commitments and its feature lists as guesses.

## Why `template` is still the default

`DEFAULTS` in `aptitude/config.py:11` still reads `"synth": "template"`. The V2 spec put it in writing too — its §3 non-goals opens with "Changing the default synthesizer (stays `template`)." A feature that ships and does not become the default invites the obvious question.

The answer is about who a default is for. `template` is three `llm.generate()` calls and needs nothing from a provider beyond completing text, which is why it runs against `FakeProvider`, fourteen lines that implement `generate()` and nothing else. `agentic` needs `chat()` and a model that reliably emits tool calls. When it doesn't get one, the loop spends its whole `--max-iterations` budget and runs the template synthesizer anyway, paying template's three calls on top — and template begins by distilling, which is not a fixed cost. [The Architect's View](../engineering/architecture.md) does that arithmetic; on a large corpus the fallback is nowhere near free.

So on a strong model `agentic` reads selectively and critiques itself once; on a weak one it costs more than `template` and returns what `template` would have. A default runs for someone who typed the command without reading this page, on whatever provider was already configured. It has to be the option whose bad day is "less interesting", not "more expensive, then less interesting".

One thing `template` does not deserve credit for, though the spec asked for it in §2: "Be deterministic and unit-testable." The call structure is deterministic — same three calls, same order, every run. The output is not. Searching `aptitude/` for `temperature`, `seed`, or `top_p` returns nothing, so two identical runs can produce two different skills.

## What is missing is measurement

Nothing in this repository scores a generated skill. `validate_draft` checks the name against `^[a-z0-9]+(-[a-z0-9]+)*$`, caps it at 64 characters, requires a non-empty description under 1024, and warns when the body is under 40 (`aptitude/validate/validator.py:18-28`). That is well-formedness. A skill can pass all of it and be about nothing — [the anatomy page](anatomy.md) documents a real run that did. So "agentic produces better skills" rests on somebody having read some output, and a claim like that stays true-sounding for years without being checked. It is why [decision 7](../engineering/decisions.md) — exactly one forced self-critique — is a guess with a number on it rather than a tuned parameter.

The smaller version is worse, because the one signal that exists never reaches the user. When the agent fails to converge, `(agentic did not converge → template fallback)` is appended to the draft's `provenance` list (`aptitude/synthesize/agentic.py:26`). Searching `aptitude/export/` for `provenance` returns nothing; `ClaudeSkillExporter` writes name, description, body, references and scripts (`aptitude/export/claude_skill.py:18-27`). Call the library and you can tell which synthesizer produced a draft. Run the CLI and you cannot.

Report the fallback, then build the scoring, and the critique count stops being a preference. That ordering is [the roadmap](roadmap.md).

[^1]: The §11 text in the repository today names the four tools that shipped, because it was corrected afterwards — not foresight. Decision 3 on [the decisions page](../engineering/decisions.md) has both commit hashes.
