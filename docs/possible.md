# The Art of the Possible

Aptitude's four ingestion adapters are named after file formats — `pdf`, `epub`, `web`, `github` are the four branches of `detect_kind()` (`aptitude/ingest/base.py:15-32`). That invites a narrow reading: point it at a document, get a better document out. Feed it a manual, get a skill that answers questions about the manual.

That reading undersells the tool, and the amount of prompt built into the pipeline is why. [why.md](why.md) puts the reason plainly: "the artifacts say what is true, the prompt says what is relevant." The corpus doesn't decide what the skill is for; the prompt does. [The anatomy page](product/anatomy.md) shows this from the other direction — pointed at `octocat/Hello-World`, whose entire README is the one line `Hello World!`, Aptitude produced a full skill about conventional commit messages anyway, because almost none of the body came from the source at all. If the sourcing can be that thin and the output still validates, "feed it documentation" was never the load-bearing part. What Aptitude does is turn a prompt plus whatever text you hand it into something shaped like a skill. The prompt supplies the purpose; the artifacts supply grounding when there's grounding to be had.

Once the source doesn't have to be documentation, the more interesting inputs are the ones nobody wrote to be read as prose in the first place: a spec aimed at one audience, retargeted at another; a repository nobody documented for newcomers; a standard long enough that nobody rereads it before every decision; several unrelated things that only become one thing once somebody, or something, reconciles them.

## Recipes that work today

Four commands, each checked against `python -m aptitude create --help` and `detect_kind()` (`aptitude/ingest/base.py`). Every `-i` value below is a real, valid artifact reference for its type — none of them is a `.md` path, because `detect_kind()` doesn't recognize one. That gap matters enough to get its own section, at the end of this page.

### 1. A spec becomes a reviewer

```bash
aptitude create \
  -p "Review a pull request diff against this design doc; flag any change that contradicts a stated invariant and cite the section it violates" \
  -i api-design-spec.pdf \
  --provider claude
```

A design doc states its invariants once, in prose, and trusts every reviewer to remember them. What comes out here is a checklist, not a restatement — the generated `SKILL.md` description has to fit in 1024 characters and its name has to match `^[a-z0-9]+(-[a-z0-9]+)*$` (`aptitude/validate/validator.py:18-24`), so the spec has to be compressed into a trigger and a set of checks rather than reproduced.

### 2. A repo becomes an onboarding guide

```bash
aptitude create \
  -p "Onboard a new engineer to this repository: explain what it does, how it's laid out, and where to start reading" \
  -i psf/requests \
  --provider ollama
```

`psf/requests` is bare `owner/repo` shorthand — valid because the owner segment has no dot in it (`aptitude/ingest/base.py:30`). The GitHub adapter then reads every `README*`, every `docs/**/*.md` truncated to 4000 characters, and function/class signatures from seven source extensions (`aptitude/ingest/github.py:37-55`) — roughly the pass a new hire makes in their first hour, done once by the adapter instead of once per hire, and at no API cost since `ollama` needs no key.

### 3. A standard becomes a linter

```bash
aptitude create \
  -p "Extract the concrete, checkable rules this standard imposes; phrase each as a pass/fail check a reviewer can run" \
  -i pci-dss-v4.pdf \
  --provider claude \
  --budget 12000
```

`distill()` only summarizes a corpus once it exceeds `--budget` (`aptitude/process/summarizer.py:18-21`). Raising the budget for a long standard keeps more of the source text intact going into synthesis, instead of asking a map-reduce summarization pass — which is told to preserve "key facts, terminology, and steps," not exact wording (`aptitude/process/summarizer.py:13-14`) — to hand back precise rule text it was never asked to preserve.

### 4. Many sources become one skill

```bash
aptitude create \
  -p "Build a skill for implementing our webhook integration: follow the spec, match the reference implementation's conventions, and use the terms from the getting-started guide" \
  -i webhook-spec.pdf \
  -i acme/webhooks-sdk \
  -i https://docs.acme.dev/webhooks/getting-started \
  --provider claude
```

`-i` is repeatable, and `--type auto` — the default — detects each one independently, so this one command runs a `.pdf` path, bare `owner/repo` shorthand, and an `https://` URL through three different adapters and distills all three into a single corpus. Reconciling three sources' terminology by hand is the actually tedious part, and `TemplateSynthesizer` does it while also recording exactly which raw inputs went in: `SkillDraft.provenance` is set to `[d.source.raw for d in docs]` (`aptitude/synthesize/template_synth.py:28`).

One limit worth stating plainly here: that provenance list is preserved in the pipeline, not in what lands on disk. `grep provenance aptitude/export/` turns up nothing — `ClaudeSkillExporter` writes the frontmatter, the body, references and scripts, and stops (`aptitude/export/claude_skill.py`). [limitations.md](limitations.md) and [the roadmap](product/roadmap.md) already track "Write `provenance` into the exported skill" as an open near-term gap, not a design choice, so don't expect to recover which source contributed what from the output directory — only from calling the library directly.

## What isn't possible yet

Two extensions are obvious enough to want, and neither is real today.

The four recipes above all produce a skill that tells an agent what to check or how to proceed. None of them produce a skill that acts on its own — opens the review comment, runs the lint, writes the file. `SkillDraft` has `scripts` and `tools` fields (`aptitude/models.py:48-49`), and neither synthesizer has ever filled them in: both `SkillDraft(...)` calls set `name`, `description`, `body`, `references`, and `provenance`, and stop there (`aptitude/synthesize/template_synth.py:25-28`, `aptitude/synthesize/agentic.py:49-54`). [The roadmap](product/roadmap.md) puts this in Far, behind an open question about whether generated code should ever be written to disk unreviewed — a question this page has no more of an answer to than that one does.

The better ending is recursive, and it's worth being honest about rather than treating as a clean punchline. This repository's own design history — the dated specs and plans under `docs/superpowers/specs/` and `docs/superpowers/plans/` — is exactly the kind of material a synthesizer turns into a skill: written before the code, stating what someone working on this codebase should know before they start. Point Aptitude at itself and, in principle, it should be able to write the onboarding skill for its own next contributor.

It can't, directly, today. Every file under `docs/superpowers/` is markdown, and `detect_kind()` has exactly four branches — `.pdf`, `.epub`, an `http(s)://` URL, or bare `owner/repo` shorthand (`aptitude/ingest/base.py:15-32`) — none of which matches a local `.md` path. Passing one raises `IngestionError`, with the message `cannot detect artifact type for '<path>'` (`aptitude/ingest/base.py:32`) — the same wall [the anatomy page](product/anatomy.md) hits when it explains why its own example run uses a GitHub repo instead of a markdown file. There is no branch for "a markdown file on disk," so the recursive idea is blocked on an ingestion gap, not a synthesis one.

The indirect route does work today: point the GitHub adapter at the whole repository, using the same bare `owner/repo` shorthand as recipe 2 — `VikrantKurada/Aptitude`, per this repo's own CI badge in `README.md` — and it clones the repository and reads `docs/**/*.md`, truncated to 4000 characters per file (`aptitude/ingest/github.py:39-45`). That does reach the specs and plans. It reaches them folded in alongside every other page under `docs/`, each one cut off partway through if it runs long, sharing one corpus with every `README*` file and every function signature the adapter also extracts from source. That's a coarser thing than "point at one spec, get its reviewer" — it's "point at the whole repository, get whatever a 6000-token budget leaves room for."

And ingestion is only half of what's missing. Nothing in this codebase scores a `SkillDraft` — `validate_draft` checks that a name matches a regex and a description fits under 1024 characters (`aptitude/validate/validator.py:18-28`), which is well-formedness, not judgment. A skill Aptitude writes about working on Aptitude is exactly the kind of output nobody here has a way to check except by reading it, and [the roadmap](product/roadmap.md) already names a scorer as the thing everything else in that section is waiting on. The loop closes. It doesn't close cleanly, and nothing yet grades what comes out the other end.
