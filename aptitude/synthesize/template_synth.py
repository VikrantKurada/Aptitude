import re
from aptitude.models import SkillDraft, SkillFile
from aptitude.synthesize.base import Synthesizer, synth_registry
from aptitude.synthesize import prompts
from aptitude.process.summarizer import distill

def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return s[:64] or "generated-skill"

@synth_registry.register("template")
class TemplateSynthesizer(Synthesizer):
    name = "template"
    def __init__(self, budget: int = 6000):
        self.budget = budget
    def synthesize(self, prompt, docs, llm) -> SkillDraft:
        corpus = distill(docs, llm, self.budget)
        nd = llm.generate(prompts.name_desc_prompt(prompt, corpus))
        name = _slug(re.search(r"name:\s*(.+)", nd).group(1) if re.search(r"name:", nd) else "skill")
        desc_m = re.search(r"description:\s*(.+)", nd, re.S)
        description = (desc_m.group(1).strip() if desc_m else prompt)[:1024]
        body = llm.generate(prompts.body_prompt(prompt, corpus)).strip()
        ref = llm.generate(prompts.reference_prompt(prompt, corpus)).strip()
        return SkillDraft(
            name=name, description=description, body=body,
            references=[SkillFile("references/source-material.md", ref)],
            provenance=[d.source.raw for d in docs])
