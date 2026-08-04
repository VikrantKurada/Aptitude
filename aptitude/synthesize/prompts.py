def name_desc_prompt(user_prompt, corpus):
    return [{"role": "user", "content":
        "You are creating a reusable AI skill. Based on the user's goal and the source "
        "material, output exactly two lines:\nname: <kebab-case-slug, max 64 chars>\n"
        f"description: <one line 'Use when…' trigger, max 1024 chars>\n\n"
        f"USER GOAL:\n{user_prompt}\n\nSOURCE MATERIAL:\n{corpus[:6000]}"}]

def body_prompt(user_prompt, corpus):
    return [{"role": "user", "content":
        "Write the body of a skill as markdown instructions that an AI assistant will "
        "follow to accomplish the user's goal, grounded in the source material. Be "
        f"concrete and actionable.\n\nUSER GOAL:\n{user_prompt}\n\nSOURCE:\n{corpus[:8000]}"}]

def reference_prompt(user_prompt, corpus):
    return [{"role": "user", "content":
        "Distill the source material into a concise reference document (facts, "
        "terminology, procedures) that supports the skill. Markdown.\n\n"
        f"GOAL:\n{user_prompt}\n\nSOURCE:\n{corpus[:8000]}"}]
