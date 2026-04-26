def load_file(path):
    with open(path, "r") as f:
        return f.read()


def build_prompt(agent_name, skill_path, dynamic_input):
    soul = load_file(f"app/souls/{agent_name}.SOUL.md")
    system = load_file(f"app/prompts/{agent_name}.txt")
    skill = load_file(skill_path)

    prompt = f"""
{{
STATIC (CACHED PART)
}}

[SYSTEM IDENTITY]
{soul}

[OPERATING RULES]
{system}

[SKILL]
{skill}

{{DYNAMIC PART}}

{dynamic_input}
"""

    return prompt
