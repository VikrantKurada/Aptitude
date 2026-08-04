from aptitude.models import SkillDraft
from aptitude.synthesize.base import Synthesizer, synth_registry
from aptitude.synthesize.agent_tools import Toolbox, TOOL_SPECS
from aptitude.synthesize.template_synth import TemplateSynthesizer, _slug
from aptitude.synthesize import agent_prompts

class _AgentDidNotConverge(Exception):
    pass

@synth_registry.register("agentic")
class AgenticSynthesizer(Synthesizer):
    name = "agentic"
    def __init__(self, budget: int = 6000, max_iterations: int = 12, fallback: bool = True):
        self.budget = budget
        self.max_iterations = max_iterations
        self.fallback = fallback

    def synthesize(self, prompt, docs, llm) -> SkillDraft:
        try:
            return self._run_agent(prompt, docs, llm)
        except _AgentDidNotConverge as e:
            if not self.fallback:
                from aptitude.errors import SynthesisError
                raise SynthesisError(f"agentic synthesis did not converge: {e}")
            draft = TemplateSynthesizer(budget=self.budget).synthesize(prompt, docs, llm)
            draft.provenance.append("(agentic did not converge → template fallback)")
            return draft

    def _run_agent(self, prompt, docs, llm) -> SkillDraft:
        tb = Toolbox(docs, read_budget=self.budget)
        messages = [{"role": "system", "content": agent_prompts.system_prompt(prompt)},
                    {"role": "user", "content": "Begin."}]
        critique_done = False
        for _ in range(self.max_iterations):
            turn = llm.chat(messages, TOOL_SPECS)
            messages.append({"role": "assistant", "content": turn.text, "tool_calls": turn.tool_calls})
            if not turn.tool_calls:
                messages.append({"role": "user", "content": "Use a tool, or call finish."})
                continue
            call = turn.tool_calls[0]
            if call.name == "finish":
                if not critique_done:
                    critique_done = True
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "name": "finish", "content": agent_prompts.CRITIQUE_NUDGE})
                    continue
                a = call.arguments
                return SkillDraft(
                    name=_slug(a.get("name", "skill")),
                    description=(a.get("description") or prompt)[:1024],
                    body=a.get("body", ""),
                    references=list(tb.references),
                    provenance=[d.source.raw for d in docs])
            result = tb.dispatch(call.name, call.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result})
        raise _AgentDidNotConverge(f"no finish within {self.max_iterations} iterations")
