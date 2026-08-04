from dataclasses import dataclass, field
from pathlib import Path
from aptitude.models import Source, SkillDraft
from aptitude.ingest.base import load
from aptitude.synthesize.base import synth_registry
from aptitude.process.summarizer import distill
from aptitude.validate.validator import validate_draft
from aptitude.export.base import export_registry
import aptitude.synthesize.template_synth  # noqa  (register)
import aptitude.export.claude_skill  # noqa

@dataclass
class RunConfig:
    prompt: str
    sources: list[Source]
    provider: str
    model: str | None
    formats: list[str]
    out: Path
    budget: int = 6000
    dry_run: bool = False
    synth: str = "template"
    max_iterations: int = 12

@dataclass
class RunResult:
    draft: SkillDraft | None
    written: list[Path] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corpus: str | None = None
    exit_code: int = 0

def run(cfg: RunConfig, provider) -> RunResult:
    docs, skipped = [], []
    for src in cfg.sources:
        try:
            docs.append(load(src))
        except Exception as e:
            skipped.append((src.raw, str(e)))
    if not docs:
        return RunResult(draft=None, skipped=skipped, exit_code=2)
    if cfg.dry_run:
        return RunResult(draft=None, skipped=skipped,
                         corpus=distill(docs, provider, cfg.budget),
                         exit_code=1 if skipped else 0)
    synth_cls = synth_registry.get(cfg.synth)
    try:
        synth = synth_cls(budget=cfg.budget, max_iterations=cfg.max_iterations)
    except TypeError:
        synth = synth_cls(budget=cfg.budget)   # template ignores max_iterations
    draft = synth.synthesize(cfg.prompt, docs, provider)
    warnings = validate_draft(draft)
    written = []
    for fmt in cfg.formats:
        written += export_registry.get(fmt)().export(draft, cfg.out)
    return RunResult(draft=draft, written=written, skipped=skipped,
                     warnings=warnings, exit_code=1 if skipped else 0)
