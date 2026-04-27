import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SOULS_DIR = BASE_DIR / "souls"
PROMPTS_DIR = BASE_DIR / "prompts"
SKILLS_DIR = BASE_DIR / "skills"


def load_file(path):
    # Файлы .SOUL.md лежат в souls/, остальные в prompts/
    if path.endswith(".SOUL.md"):
        full_path = SOULS_DIR / path
    elif not os.path.isabs(path):
        full_path = PROMPTS_DIR / path
    else:
        full_path = path
    
    with open(full_path, "r") as f:
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