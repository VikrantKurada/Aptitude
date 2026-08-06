# Aptitude — Nested Documentation: Design

**Status:** Approved (design phase)
**Date:** 2026-08-06
**Owner:** VikrantKurada

## 1. Summary

Replace the single 195-line reference README with a nested documentation tree: a slim
`README.md` front door that routes readers, plus a `docs/` hierarchy of essays and
reference pages covering what Aptitude is, why it exists, how it was decided, how it is
built, where it goes, and what it can be pushed to do.

Essays are written in Paul Graham's register — short declarative sentences, concrete
before abstract, candid about mistakes, no marketing language. Reference pages stay
plain. That split is load-bearing: PG-voiced CLI flag tables would be unreadable.

## 2. Goals

- Give five distinct audiences a one-hop path to the page they want.
- Make the reasoning behind the product legible, not just its surface.
- State the spec-versus-code gaps explicitly rather than letting a reader discover them.
- Keep the tree verifiable — no build step, no broken cross-links.

## 3. Non-goals

- A generated docs site (MkDocs, GitHub Pages). Plain markdown, GitHub-rendered.
- Changes to `aptitude/` source. This is documentation plus one test change.
- Tutorials, screencasts, or API-level docstring reference.

## 4. Audiences

The README's primary job is routing, because five audiences read this repo:

| Reader | Wants | Lands on |
|---|---|---|
| Curious | What is this, conceptually | `docs/why.md` |
| Evaluating | Does it solve my problem | `README.md` → `docs/product/features.md` |
| Judging the work | Evidence of judgment | `docs/engineering/decisions.md` |
| Contributing | Where the seams are | `docs/engineering/extending.md` |
| Future maintainer | Why it was done this way | `docs/engineering/decisions.md` |

## 5. Structure

```
README.md                        front door: what it is, 60-second demo, routing table
docs/
  index.md                       the map
  why.md                         Why Aptitude Exists                    [essay]
  product/
    features.md                  What It Does                           [reference]
    anatomy.md                   Anatomy of a Generated Skill           [reference]
    perspective.md               The Product Manager's View             [essay]
    roadmap.md                   Where This Goes                        [essay + table]
  engineering/
    architecture.md              The Architect's View                   [essay + mermaid]
    decisions.md                 Key Decisions                          [essay-ADRs]
    extending.md                 Adding a Provider, Format, or Adapter  [reference]
  possible.md                    The Art of the Possible                [essay + recipes]
  limitations.md                 What It Doesn't Do Yet                 [candid reference]
```

Two levels, split product from engineering, mirroring the audience split. Existing
`docs/superpowers/` (specs and plans) is untouched and gets a pointer from `docs/index.md`.

## 6. Page contracts

Each page has one job. If a page needs to do two, it splits.

**`README.md`** — Under 120 lines. What Aptitude is in two sentences, install, one
worked example with real output, the provider/format tables (kept here because they
answer "can I use this?"), and the routing table. Everything else is a link.

**`docs/index.md`** — The map. One line per page saying who it is for.

**`docs/why.md`** — Skills became the unit of reuse for agents, but the knowledge that
belongs in them already exists in PDFs, repos, and docs sites. The bottleneck was never
knowing things; it is *shaping* what you know into a form an agent can act on. That
reshaping is mechanical, so it can be automated.

**`docs/product/features.md`** — Reference. Commands, flags, providers, formats,
synthesizers, configuration precedence. Inherits most of the current README body.

**`docs/product/anatomy.md`** — Reference. A real generated skill directory, annotated:
what `SKILL.md` frontmatter must satisfy, what `references/` holds, what each export
format emits and when to pick it. Nothing else documents the output shape.

**`docs/product/perspective.md`** — Essay. The v1 spec deferred agentic synthesis and
shipped a fixed three-call template instead. That looks like timidity and was the
strategy: the boring version proved the pipeline, and when the interesting version
arrived it plugged into a seam already waiting for it. Also argues why `template`
remains the default after `agentic` shipped.

**`docs/product/roadmap.md`** — Essay framing plus a table. Every near-term item traces
to a verified gap in §7, which is what separates a roadmap from a wish list.

**`docs/engineering/architecture.md`** — Essay with mermaid diagrams. `SkillDraft` is the
pivot: five providers times five formats times two synthesizers is fifty working
combinations from ~1,400 lines, because none of them know about each other. Second
insight: `LLMProvider.chat()` defaults to a ReAct text protocol, so the agent loop runs
on models with no tool API at all — native tool-calling became an optimization rather
than a requirement.

**`docs/engineering/decisions.md`** — Seven decisions, each as: what was chosen, what was
rejected, **and what would change our mind.** The third clause is the one that matters
later and the one almost nobody writes. Covers: pluggable pipeline over monolith;
`SkillDraft` as pivot; template-first; ReAct default with native override; agentic falls
back to template rather than failing; no filesystem or network tools for the agent;
forced single self-critique.

**`docs/engineering/extending.md`** — Reference. Three worked walkthroughs — new provider,
new exporter, new ingestion adapter — each showing the ABC, the registry call, and the
contract test the new component must pass.

**`docs/possible.md`** — Essay plus recipes. What works today (a spec into a reviewer
skill, a repo into an onboarding skill, an RFC into a linter), then honest speculation,
ending on Aptitude generating skills for the agent that runs Aptitude.

**`docs/limitations.md`** — The verified gap table from §7, each entry naming its
evidence and linking to its roadmap item.

## 7. Verified gaps

Confirmed by reading the code, not inferred from the spec. These populate
`limitations.md` and seed the near-term roadmap.

| Gap | Evidence |
|---|---|
| No caching; web and GitHub refetch every run | `config.py:10` defines `"cache"`, nothing reads it; no `--no-cache` flag |
| Token counting is `len(text) // 4` everywhere | `process/tokens.py`; spec §9 promised exact counts with a tiktoken fallback |
| `context_window` declared but unused by the pipeline | Providers declare 200k/1M/8k; `distill()` sizes against the flat `--budget` default of 6000 |
| No retries or backoff | No occurrences of retry, backoff, or sleep in `aptitude/`; spec §14 promised bounded retries |
| `SkillDraft.scripts` and `.tools` are never populated | No synthesizer emits them, so `mcp-manifest` always exports an empty tool list |
| `--base-url` is TOML-only | Read by the ollama and openai factories, never exposed as a CLI flag or documented |
| `max_tokens_budget` is a dead config key | `DEFAULTS` defines it; the CLI's `--budget` carries its own default and the key is never read |

## 8. Voice

Applies to essays only (`why`, `perspective`, `roadmap`, `architecture`, `decisions`,
`possible`).

- Short declarative sentences. Concrete example before the abstraction.
- Admit what was wrong or surprising. Candor is more persuasive than polish.
- No marketing register: no "powerful", "seamless", "revolutionize", no exclamation points.
- Prose paragraphs, not bullet stacks. Bullets are for reference pages.
- Numbered footnotes for asides worth keeping but not worth interrupting for.
- Framed as reasoning, not roleplay. "Here is the call and here is what would have
  changed it" — never "as a Product Manager, I…".

## 9. Testing

`tests/test_readme_examples.py:12` asserts every provider name appears in `README.md`.
Moving content into `docs/` breaks it. Rather than weaken the assertion, widen it to
cover the tree — broken cross-links are how multi-page docs rot.

Replace with `tests/test_docs.py`:

- Every provider in `config.DEFAULT_MODELS` appears somewhere in `README.md` + `docs/**.md`.
- Every name in `export_registry` appears in the docs tree.
- Every CLI command (`create`, `providers`, `formats`, `validate`, `init`) appears.
- Every relative markdown link in `README.md` and `docs/**.md` resolves to a file that
  exists. Anchors are not validated; external URLs are skipped.
- Retain the existing `--help` exit-code check for all commands.

Scope the link check to `README.md` and `docs/`, excluding `docs/superpowers/`, whose
plan files contain illustrative paths that are not real links.

## 10. Risks

- **Discoverability.** Content behind a link is read less than content in the README.
  Mitigated by keeping the tables that answer "can I use this?" in the README, and by
  making the routing table the last thing on the page.
- **Drift.** Nine pages drift from the code faster than one. Mitigated by the tests in
  §9, and by keeping `features.md` the single home for flag-level detail so there is
  one place to update.
- **Voice drift into parody.** PG's register is easy to overshoot. The rule in §8 —
  reasoning, not persona — is the guard.

## 11. Open questions

None blocking.
