import os
from app.llm.llm_client import LLMClient
from app.utils.prompt_builder import build_prompt

llm = LLMClient()
agent_name = os.getenv("AGENT_NAME", "planner")


def run_planner(prompt, skill="planner/build_roadmap.md", agent_name=agent_name):
    full_prompt = build_prompt(agent_name, skill, prompt)

    return llm.generate(
        full_prompt,
        agent_name=agent_name,
        metadata={"skill": skill, "type": "planner"}
    )
