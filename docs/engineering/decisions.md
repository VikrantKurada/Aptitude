# Key Decisions

Seven calls, each with the alternative it beat and the thing that would undo it. The third part is the one worth writing down. A decision recorded without a falsifier is an assertion with a date on it — it tells a later reader what happened and gives them nothing to check it against.

Several of these were written down before implementation, which is the only reason the rejected alternatives here are trustworthy: the v1 design spec's §3 non-goals and §11 extension point, and the V2 spec's §4, headed "Key decisions (from brainstorming)". Where an alternative is quoted, it was rejected at the time and not in hindsight.

The mechanics behind decisions 4 and 5 are in [The Architect's View](architecture.md); the sequencing argument behind decision 3 is expanded in [the product view](../product/perspective.md). The prior question — why reshaping documents into skills is worth automating at all — is [a different essay](../why.md).

## 1. A pluggable pipeline, not a monolith

**The call.** Four stages — ingest, process, synthesize, export — each a registry keyed by a string, each component selected at runtime by name. The v1 spec chose this in §4 and set its own acceptance test in §2: "extension never requires touching the pipeline."

**What was rejected.** A single orchestrator. The spec named it and named its advantage honestly — "fewer abstractions, faster to start" — before rejecting it. That advantage was real, and it was paid up front. `Registry`, four instances of it, four abstract base classes and two shared contract-test helpers all had to exist before the first skill was ever generated.

**What would change my mind.** The component count, and nothing else. Five providers, five formats and two synthesizers give fifty combinations out of twelve implementations. Two providers, one format and one synthesizer would give two combinations out of four implementations, and at that size four registries are more machinery than the thing they organize. Break-even is somewhere around ten combinations. What made the bet safe was not the pattern but §2 of the spec committing to five providers and five formats in writing before a line was written; had that list been aspirational, the abstractions would have been overhead with a plan attached. Pluggability is not a good default. It is a wager on a component count, and the honest version of this decision is that the wager was explicit and it happened to pay.

## 2. `SkillDraft` as the pivot

**The call.** One dataclass in the middle, and both halves of the program talk to it instead of to each other (`aptitude/models.py:42-50`). The v1 spec §6 already called it "the pivot" and gave the reason: it "keeps providers and formats independent of each other." How that plays out mechanically is [The Architect's View](architecture.md#the-pivot); what matters here is the counting.

**What was rejected.** Letting exporters read provider output directly — have `ClaudeSkillExporter` parse whatever `template` returns, and teach each new exporter about each synthesizer. That is a pairing problem. Two synthesizers and five formats is ten adapters to write and keep correct, and a third synthesizer makes it fifteen. Through the pivot it is two producers and five consumers, and a new one on either side costs one.

**What would change my mind.** A format that needs something the draft cannot represent. The draft is strings all the way down: `SkillFile` is `relpath: str` and `content: str` (`models.py:31-34`). A skill that has to ship a binary — a compiled helper, an image, a wheel — has nowhere to live, and the fix would be to widen `SkillFile` to bytes, which touches every exporter at once. That is the shape of change a pivot cannot absorb: not a new component, but a new kind of payload. The error today runs the other way. Two of the draft's seven fields, `scripts` and `tools`, have never been populated by anything ([limitations.md](../limitations.md)), so the pivot is over-specified rather than under-specified — the cheaper of the two mistakes, and not one that was planned.

## 3. Template synthesis first, agentic deferred

**The call.** v1 shipped a fixed three-call sequence — name and description, then body, then reference material (`aptitude/synthesize/template_synth.py:18-24`) — and wrote the deferral down instead of leaving it implied. The v1 spec's §3 non-goals says it plainly: agentic synthesis, "**Deferred to V2**; the architecture reserves a plug-in point for it (see §11)."

**What was rejected.** Building the interesting version first.

**What would change my mind.** Nothing, in hindsight. This is the decision I would repeat most confidently, which makes it the one where naming the falsifier matters most, because confidence without one is just preference.

A deferral is only cheap if the seam is right, and the seam here was written before v1 shipped. `pipeline.py` was created with `synth: str = "template"` and a `synth_registry.get(cfg.synth)` lookup already in it. `git log -- aptitude/pipeline.py` returns two commits in total; the second added `max_iterations` plumbing, not a branch for the new synthesizer. `AgenticSynthesizer` registered itself with a decorator and `run()` never learned it existed. Had the agent loop needed something `Synthesizer.synthesize(prompt, docs, llm) -> SkillDraft` could not express — a second provider, a streaming channel, an export path of its own — the seam would have been the wrong shape and the deferral would have cost more than building agentic first. It didn't; both synthesizers have that identical signature (`aptitude/synthesize/base.py:7-10`).

What is worth noticing is how little of the deferral's *content* survived. The §11 text in this repository today names the four tools that shipped, but that is a later correction (commit `50c8a50`). The version written on 3 August guessed the toolset as `read_artifact`, `summarize`, `write_file` (commit `0acfd2b`). What got built was `list_sources`, `read_source`, `add_reference`, `finish`. Zero of three survived. The seam held and the guess about what would plug into it was wrong in every particular — which is the argument for deferring against a written interface rather than a written feature. Defer with a seam and you are sequencing. Defer without one and you are just not building it.

## 4. ReAct as the default, native tool-calling as an override

**The call.** `LLMProvider.chat()` is not abstract. It has a working six-line body that flattens the transcript and a tool catalog into one text prompt and parses a fenced JSON action block back out (`aptitude/llm/base.py:33-38`). The V2 spec recorded it in §4 as "Tool mechanism: Hybrid," with native overrides scoped to all five providers.

**What was rejected.** Making `chat()` abstract and requiring native tool support. Tool-calling was uneven at the time — the v1 spec had already cited "tool-calling support is uneven across Ollama/NVIDIA" in §4 as one reason to defer agentic synthesis at all. Requiring it would have made `--synth agentic` a feature of the hosted providers only. It would also have excluded `FakeProvider`, fourteen lines implementing nothing but `generate()`, which is what lets the agent loop be tested offline.

**What would change my mind.** Every target provider gaining reliable native tools. All five real providers already override `chat()`, so against a real API the text protocol almost never runs; what keeps it alive is `FakeProvider` and small local models behind an OpenAI-compatible endpoint. Unusually for this list, the falsifier is countable: how often a run reaches `base.chat()` instead of an override. If that number went to zero and stayed there — local tool support having become reliable, and the tests having moved onto mocked native paths — then `tools_react.py` would be dead weight carrying a live risk, since its parse is a regex over free prose and will happily execute an action block the model only quoted. I would delete it and make `chat()` abstract. Nothing counts that today, which is the weak point in this entry rather than in the decision.

## 5. Agentic falls back to template instead of failing

**The call.** `_AgentDidNotConverge` and `ProviderError` are both caught, `TemplateSynthesizer` runs instead, and `"(agentic did not converge → template fallback)"` is appended to the draft's provenance (`aptitude/synthesize/agentic.py:19-27`).

**What was rejected.** Raising `SynthesisError`. That path still exists — `fallback=False` does exactly it (`agentic.py:23-24`) — but neither `cli.py` nor `pipeline.py` ever sets the flag, so it is a library option and not a user-facing one. The reasoning is about sunk cost rather than robustness in general. By the time the agent loop starts, the user has already paid for a shallow clone or an HTTP fetch. Failing there returns nothing for all of it. Falling back returns a skill that is merely less interesting — though not for free itself: the fallback runs `template`, which chunks and possibly summarizes the corpus, spending one provider call per chunk. What that costs in additional provider calls is worked out in [The Architect's View](architecture.md).

**What would change my mind.** Evidence that a silent fallback had hidden a systematic failure — a provider whose tool support quietly broke, where every run still exits 0 and reads like a successful `--synth agentic`. The mitigation is meant to be the provenance line, and it is weaker than it looks: no exporter writes `provenance` to disk. Call the library and you can see which path produced a draft; read the output directory and you cannot. So the fallback today is recorded, not reported. That gap, not the fallback itself, is what would flip this decision, and the fix is small — print the line from the CLI, or put it in the `SKILL.md` frontmatter. Until one of those exists, this decision leans on a promise the output does not keep.

## 6. No filesystem or network tools for the agent

**The call.** Four tools, none of which touch the disk or the network (`aptitude/synthesize/agent_tools.py:6-19`). `read_source` serves `Document` objects already in memory; `add_reference` appends to a Python list. The V2 spec put it in §3 as a non-goal in writing and restated it in §10 under limits.

**What was rejected.** Letting the agent fetch what it decides it needs. That is the more useful agent, and it is not a straw man — the v1 spec's own guess at the toolset included `write_file`. An agent with a fetch tool would notice the RFC a PDF cites and go read it, and would notice that a repo's real documentation lives on a site rather than in `docs/`.

**What would change my mind.** Very little, and there is a piece of history that is the reason. Even with no filesystem tool at all, `add_reference` had to be hardened: it now rejects empty paths, absolute paths, `..` segments and Windows drive letters (`agent_tools.py:51-56`). That check did not ship with the tool. It arrived in a later fix commit (`e4c88cd`), and drive-absolute paths needed a second one after that (`73a22cc`). A tool whose entire effect is appending to a list still produced a string that an exporter would later turn into a path on disk. The blast radius of an agent tool is not where the tool runs; it is wherever its output eventually lands, which is one step further away than it looks. A bounded extension I would consider: a read-only fetch restricted to URLs that already appear in an ingested document. An open `read_file` I would not, at any `--max-iterations`, because the iteration cap bounds how many times the agent acts and says nothing at all about what a single action can reach.

## 7. Exactly one forced self-critique

**The call.** The first `finish` is refused. A flag flips, the agent gets a critique prompt back as the tool result, and only the second `finish` builds the draft (`aptitude/synthesize/agentic.py:33`, `42-47`). That round consumes one of `--max-iterations` like any other turn; it does not add one on top of the budget.

**What was rejected.** Zero and unbounded, for different reasons. Zero produced drafts that read as weaker — descriptions that restated the prompt rather than narrowing it into a trigger. Unbounded costs one provider call per extra round with no reason to expect the fourth to add what the second did.

**What would change my mind.** Scoring, which does not exist. Nothing in this repository evaluates a generated skill. `validate_draft` checks that the name matches `^[a-z0-9]+(-[a-z0-9]+)*$` and is at most 64 characters, that the description is non-empty and at most 1024, and warns when the body is under 40 characters (`aptitude/validate/validator.py:18-28`). That is well-formedness, not quality. So "one" is not a tuned number. It is a guess that survived reading the output, and two would be defensible on exactly as much evidence, which is to say none. This is the only one of the seven where there is no fact to point at, which makes it the first I would revisit and makes an evaluation harness the [roadmap item](../product/roadmap.md) that matters most.

[← Back to the documentation index](../index.md)
