import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_file(path):
    if not os.path.isabs(path):
        path = BASE_DIR / "prompts" / path
    
    with open(path, "r") as f:
        return f.read()


def build_prompt(agent_name, skill_path, dynamic_input):
    soul = load_file(f"{agent_name}.SOUL.md")
    system = load_file(f"{agent_name}.txt")
    
    if not os.path.isabs(skill_path):
        skill = load_file(f"../skills/{skill_path}")
    else:
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