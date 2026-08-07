# Why Aptitude Exists

The first example in Aptitude's design spec is a command that reads a privacy-law PDF, a page on gdpr.eu, and a GitHub repo, and writes one skill for drafting GDPR-compliant privacy policies. Look at the two sides of that command. Everything on the input side already existed — somebody wrote the law, somebody wrote the explainer, somebody wrote the repo. The output side is the only part that did not exist, and it contains no new information at all.

That is the situation the tool was built for, and it is not a knowledge problem.

Skills became the unit of reuse for agents because they are the smallest thing you can hand a model that changes what it does. The format makes the constraint visible. A Claude Skill is a `SKILL.md` whose name has to match `^[a-z0-9]+(-[a-z0-9]+)*$` and fit in 64 characters, whose description has to fit in 1024, and whose body is markdown (`aptitude/validate/validator.py:18-24`). The description is a "Use when…" trigger — that exact phrasing is in the system prompt Aptitude hands its own agent (`aptitude/synthesize/agent_prompts.py`). Everything a 300-page standard implies has to arrive through an opening that size.

So the scarce thing is shape, not knowledge. An agent cannot act on the standard. It needs the twelve rules the standard implies, in the form its runtime expects, small enough that loading them is not itself a decision.

Turning the first into the second is four steps: read the source, decide what matters for this purpose, compress, emit in the right format. Three of the four are already ordinary functions here. The GitHub adapter never reads a repo — it reads every `README*`, every `docs/**/*.md` truncated to 4000 characters, and from source files in seven extensions only the lines that begin a function or a class (`aptitude/ingest/github.py:37-55`). `distill()` measures the corpus against `--budget`, 6000 tokens by default, and map-reduce summarizes it when it is over (`aptitude/process/summarizer.py:18-30`). Then an exporter writes the format. Read, compress, emit: all plumbing.

The step that is not plumbing is the second one, and it is why this needs a model rather than a script. What matters depends on the purpose, and the purpose is not in the file. The same PDF makes one skill for a lawyer reviewing contracts and a different one for an engineer adding a consent banner. Nothing in the PDF distinguishes them. That is why the prompt is the first argument to `aptitude create` and the artifacts are the second — the artifacts say what is true, the prompt says what is relevant. Bulk reading under a stated purpose is mechanical work that still requires judgment, which is the thing language models are actually good at, and a bad way to spend an afternoon.

It is worth being clear about what this does not fix. The [anatomy page](product/anatomy.md) documents a real run against `octocat/Hello-World`, whose README is one line: `Hello World!`. Aptitude produced a well-formed, validating skill about conventional commit messages anyway. The shape was right and the sourcing was empty — every useful sentence came from the model's own knowledge, not from the corpus. Reshaping needs something to reshape, and nothing in the pipeline tells you when there wasn't.[^1]

The consequence is about economics rather than quality. The whole machine is about 1,371 lines of Python, and a `template` run is three provider calls against the distilled corpus (`aptitude/synthesize/template_synth.py:18-24`). Point it at `--provider ollama` and it needs no API key and no network beyond fetching the sources. The marginal cost of one more skill is a few minutes and some electricity.

Once that is true, what you optimize changes. A skill you can regenerate in ten minutes is not worth maintaining. You stop curating a library of general skills that half-fit and start making narrow ones per task — a reviewer skill for this RFC, an onboarding skill for this repo, both thrown away on Friday. The interesting number is not how many skills you keep; it is how short the gap is between wanting one and having it. Fifty provider-format-synthesizer combinations exist here not because anyone needs fifty, but so that the gap is never widened by the one you happen to want being unavailable.[^2]

That is the whole bet. Skills are cheap enough to be disposable, and most of what makes them expensive is a reading job.

[^1]: `aptitude validate` checks that the name matches the regex, that the description is non-empty and under 1024 characters, and warns when the body is under 40 characters (`aptitude/validate/validator.py:18-28`). Nothing scores whether the content is grounded in the sources. See [limitations.md](limitations.md).

[^2]: Five providers, five formats, two synthesizers. Why that multiplies instead of adding is the subject of [The Architect's View](engineering/architecture.md).
