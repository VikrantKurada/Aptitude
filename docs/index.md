# Aptitude Documentation

Ten pages. The table says who each one is for — start from the row that matches what you came for. Every page is written against the code as it stands and cites a file and a line wherever a claim needs one.

| Page | For |
|---|---|
| [Why Aptitude Exists](why.md) | Understanding the problem it solves |
| [What Aptitude Does](product/features.md) | Commands, providers, formats, configuration — the full reference |
| [Anatomy of a Generated Skill](product/anatomy.md) | What the output actually looks like, file by file |
| [The Product Manager's View](product/perspective.md) | Why it was sequenced this way |
| [Where This Goes](product/roadmap.md) | What is planned, and what is not |
| [The Architect's View](engineering/architecture.md) | How fifty combinations fit in 1,371 lines |
| [Key Decisions](engineering/decisions.md) | What was chosen, what was rejected, and what would change it |
| [Adding a Provider, Format, or Adapter](engineering/extending.md) | Contributing code |
| [The Art of the Possible](possible.md) | Recipes that work today, and where they run out |
| [What It Doesn't Do Yet](limitations.md) | Known gaps, each with file-and-line evidence |

Flag-level and option-level detail lives in [What Aptitude Does](product/features.md) and nowhere else. The other pages assume it rather than restate it.

## The archive

`docs/superpowers/specs/` and `docs/superpowers/plans/` hold the dated design documents this project was built from — the v1 spec of 3 August 2026, the V2 agentic-synthesizer spec, and the plans that executed them. They are history rather than documentation: they record what was intended on the day each was written, and the code has moved since. Where a spec and the code disagree, the code is what runs, and [What It Doesn't Do Yet](limitations.md) is the reconciliation — it lists each place the spec promised something the implementation does not do, with the line of source that settles it.
