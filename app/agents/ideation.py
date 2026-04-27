from app.llm.llm_client import LLMClient
from app.utils.prompt_builder import build_prompt

llm = LLMClient()


def run_ideation(prompt, skill="ideation/generate_idea.md", agent_name="ideation"):
    full_prompt = build_prompt(agent_name, skill, prompt)

    return llm.generate(
        full_prompt,
        agent_name=agent_name,
        metadata={"skill": skill, "type": "ideation"}
    )
