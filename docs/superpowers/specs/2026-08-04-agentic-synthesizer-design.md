# Aptitude — V2 Agentic Synthesizer: Design

**Status:** Approved (design phase)
**Date:** 2026-08-04
**Owner:** VikrantKurada
**Builds on:** [2026-08-03-aptitude-skill-generator-design.md](2026-08-03-aptitude-skill-generator-design.md) §11 (V2 extension point)

## 1. Summary

Add a second, opt-in synthesizer — `agentic` — that assembles a skill by running an
LLM **agent loop** with tools, instead of the fixed three-call `template` sequence. The
agent explores the ingested sources selectively, drafts the skill, critiques and improves
it, then finalizes. It produces the **same `SkillDraft`** as the template synthesizer, so
validation and every exporter work unchanged.

The feature is **additive and backward-compatible**: `template` stays the default;
`agentic` is selected via `--synth agentic`. Nothing in the existing
ingest/process/export/validate stages changes.

## 2. Goals

- A provider-agnostic agent loop that works with **all five providers** plus the offline
  `FakeProvider`.
- Native tool-calling for each provider where it exists, with a universal **ReAct text
  protocol fallback** so tool-less models still work.
- Selective reading of large corpora + one forced self-critique/refine cycle — the
  concrete advantages of "agentic" over the template approach.
- Robustness: the user always gets output — on non-convergence, fall back to the template
  synthesizer.
- Fully offline, deterministic tests (no network in the default suite).

## 3. Non-goals

- Changing the default synthesizer (stays `template`).
- Filesystem or network tools for the agent — it only reads already-ingested `docs` and
  accumulates references in memory.
- Streaming, multi-agent orchestration, or parallel tool execution.
- A `search_sources` keyword-index tool (possible future addition; not in this version).

## 4. Key decisions (from brainstorming)

- **Tool mechanism: Hybrid.** A new `LLMProvider.chat()` whose **default is the ReAct
  text protocol**; each provider **overrides** it with native tool-calling.
- **Native scope: all five providers** (`claude`, `openai`, `nvidia`, `gemini`, `ollama`).
- **Failure mode: fall back to `TemplateSynthesizer`** on non-convergence.
- **Toolset:** `list_sources`, `read_source`, `add_reference`, forced self-critique,
  `finish`.

## 5. Interface extension (`llm/base.py`)

The one addition to the provider abstraction:

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict            # always a Python dict (normalized from JSON if needed)

@dataclass
class AssistantTurn:
    text: str                  # assistant prose (may be "")
    tool_calls: list[ToolCall] # empty when the agent is just talking / done

class LLMProvider(ABC):
    ...
    def chat(self, messages: list[dict], tools: list[ToolSpec]) -> AssistantTurn:
        """Tool-aware turn. DEFAULT = ReAct text protocol (see llm/tools_react.py):
        render the neutral messages + a tool catalog + action syntax into one prompt,
        call self.generate(...), parse an action block into tool_calls."""
```

- Tools are described with the **existing** `ToolSpec(name, description, parameters)`
  dataclass from `models.py` (reused; `parameters` is a JSON-schema-ish dict).
- Native providers add `"tools"` to their `capabilities` set (informational).

**Neutral message format** (the only format the agent loop speaks; each provider's
`chat()` translates it internally):

- `{"role": "system", "content": str}`
- `{"role": "user", "content": str}`
- `{"role": "assistant", "content": str, "tool_calls": [ToolCall]}` (`tool_calls` optional)
- `{"role": "tool", "tool_call_id": str, "name": str, "content": str}`

## 6. ReAct default (`llm/tools_react.py`)

Used by the base `chat()` so every provider (incl. `FakeProvider`) supports tools:

- **Render:** flatten the neutral transcript into one prompt containing (a) a tool catalog
  (each tool's name, description, and JSON parameters), (b) the required **action syntax**
  — a single fenced ```action block holding `{"tool": "<name>", "arguments": {...}}` — and
  (c) the conversation so far (assistant `tool_calls` rendered as prior actions, `tool`
  results as observations).
- **Call:** `self.generate(rendered)`.
- **Parse:** extract the first well-formed action block → one `ToolCall` (id synthesized,
  e.g. `react-<n>`); prose before the block becomes `AssistantTurn.text`; no/invalid block
  → `tool_calls=[]` (agent gets to retry, prose preserved).

One tool call per ReAct step (the common ReAct convention); native paths may return
multiple in a turn.

## 7. Native provider overrides

Each provider's `chat(messages, tools)` translates neutral ↔ native, calls its API with
the tool schemas, and returns an `AssistantTurn`. Arguments are normalized to a Python
`dict` regardless of the API's representation.

| Provider | Native mapping |
|---|---|
| `claude` (`llm/claude.py`) | Neutral → Anthropic `system` param + `tool_use`/`tool_result` content blocks; `tools=[{name, description, input_schema}]`; parse response content → text + `ToolCall`s. |
| `openai` / `nvidia` (`llm/openai.py`, shared) | Neutral → OpenAI messages (`assistant.tool_calls`, `role:"tool"` + `tool_call_id`); `tools=[{type:"function", function:{name,description,parameters}}]`; parse `choices[0].message.tool_calls` (JSON-string args → dict). |
| `gemini` (`llm/gemini.py`) | Neutral → `contents` with `functionCall`/`functionResponse` parts; `tools=[{function_declarations:[…]}]`; parse candidate `functionCall`s. |
| `ollama` (`llm/ollama.py`) | `/api/chat` with `tools=[…]`, `stream:false`; parse `message.tool_calls`. |

The client-injection seams already present (httpx client for ollama/openai; injected
`.generate` client for claude/gemini) are extended so `chat()` is testable without network
or SDKs.

## 8. Agent loop (`synthesize/agentic.py`)

`AgenticSynthesizer` is registered `"agentic"` and constructed by the pipeline as
`AgenticSynthesizer(budget=cfg.budget)` (it also accepts `max_iterations` and `fallback`).
It produces the same `SkillDraft` as `template`.

**Tools** (each a `ToolSpec` + an implementation bound to `docs` + budget):

| Tool | Effect |
|---|---|
| `list_sources()` | Index of each source: number, title, `raw`, section headings. Cheap. |
| `read_source(index, section=None)` | Text of a source (or one named section), truncated to a per-read cap; cumulative chars tracked against a total read budget. |
| `add_reference(relpath, content)` | Stashes a distilled `SkillFile` under `references/`. |
| `finish(name, description, body)` | Terminal — assembles the `SkillDraft`. |

**Loop** (`max_iterations`, default 12):

1. Seed messages: a **system prompt** (`agent_prompts.py`) stating the goal (build a skill
   for the user's prompt), describing the tools, and prescribing phases — *explore →
   draft → critique & improve → finish* — plus the user's prompt as the first user message.
2. Each iteration: `turn = llm.chat(messages, TOOLS)`; append the assistant turn; run each
   `tool_call` and append a `tool` result message.
3. **Forced self-critique:** the *first* `finish` call is intercepted once — instead of
   accepting, the loop returns a `tool` result asking the agent to critique its draft
   against the goal + sources and call `finish` again with an improved version. The
   *second* `finish` is accepted. A `_critique_done` flag guarantees exactly one refine
   cycle and prevents looping.
4. On accepted `finish`: build
   `SkillDraft(name=_slug(name), description=description[:1024], body=body,
   references=<accumulated>, provenance=[d.source.raw for d in docs])`. Reuse the
   template synthesizer's `_slug` for a valid kebab-case name.

**Error handling within the loop:** a malformed tool call (bad JSON, unknown tool, missing
required args) does **not** crash the loop — it is returned to the agent as a `tool` error
message so it can self-correct, counting against the iteration budget.

## 9. Convergence & fallback

- If the loop hits `max_iterations` without an accepted `finish`, or an unrecoverable error
  occurs, `AgenticSynthesizer` **falls back to `TemplateSynthesizer(budget).synthesize(
  prompt, docs, llm)`** and appends `"(agentic did not converge → template fallback)"` to
  the draft's `provenance` so the outcome is transparent.
- `fallback=False` (not the default) instead raises `SynthesisError` with the reason.

## 10. Limits & safety

The agent calls real LLMs in a loop, so cost is bounded:

- `max_iterations` hard cap → then fallback.
- A **total read budget** derived from `budget` caps cumulative `read_source` output;
  further reads return a "read budget exhausted" notice instead of more text.
- Each `chat()` passes a bounded `max_tokens`.
- **No filesystem or network tools.** `read_source` serves only already-ingested `docs`;
  `add_reference` accumulates in memory. The agent cannot read arbitrary files or reach the
  network.

## 11. CLI & config

- **CLI (`create`):** add `--synth {template|agentic}` (default resolved via config,
  ultimately `template`) → `RunConfig.synth`. Add optional `--max-iterations N` (default
  12; ignored by `template`).
- **Config:** `synth` joins the precedence chain (CLI > `APTITUDE_SYNTH` > `aptitude.toml`
  > default `template`), mirroring `format`. `init` gains a commented `# synth = "template"`
  line. `providers` output can show which providers advertise `tools`.
- `pipeline.py` needs no change beyond the CLI feeding `synth` into `RunConfig`
  (`RunConfig.synth` and the dispatch already exist).

## 12. Testing strategy (all offline)

- **ReAct parse/render** (`tools_react`): scripted `FakeProvider` action block → correct
  `ToolCall`; plain text → empty `tool_calls`; malformed block → empty (retryable).
- **Each native override:** mocked `httpx.MockTransport` (ollama/openai/nvidia) or injected
  fake client (claude/gemini) returning a tool call → assert the `AssistantTurn`, **and**
  that a follow-up neutral `tool` result round-trips into the next request's native shape.
- **Agent loop (integration):** a `FakeProvider` scripted through a full session
  (`list_sources` → `read_source` → `add_reference` → `finish` → forced-critique →
  `finish`) → assert the `SkillDraft`. Separate tests: the **read-budget cap**, a
  **malformed-tool-call recovery**, and **max-iterations → template fallback**.
- **Provider contract:** extend the shared contract so every provider's `chat(msgs, [])`
  returns an `AssistantTurn` with a string `text`.
- Live provider tool-calling stays behind the existing `@pytest.mark.live` marker.

## 13. Documentation

- README gains a short **"Synthesizers"** section (template vs agentic, when to use each,
  the `--synth` flag, the `--max-iterations` knob).
- The v1 design spec's §11 V2 note is marked implemented.

## 14. Open questions

None blocking. Native tool-call wire formats will be confirmed against each provider's
current API during implementation (Anthropic tools, OpenAI functions, Gemini function
calling, Ollama tools); the `claude-api` skill is the source of truth for the Anthropic
shape.
