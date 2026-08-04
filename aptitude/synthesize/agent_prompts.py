def system_prompt(user_prompt: str) -> str:
    return (
        "You are building a reusable AI skill. Goal:\n"
        f"{user_prompt}\n\n"
        "Work in phases using the available tools: (1) call list_sources, then read_source "
        "to explore the material; (2) optionally add_reference to save distilled notes; "
        "(3) draft the skill; (4) critique your draft against the goal and the sources and "
        "improve it; (5) call finish with the final name, description ('Use when...'), and body. "
        "Call exactly one tool per turn."
    )

CRITIQUE_NUDGE = (
    "Before finalizing: critique this draft against the goal and the sources — is the "
    "description a precise 'Use when...' trigger? Is the body concrete and actionable? "
    "Call finish again with an improved version (or the same if already strong)."
)
