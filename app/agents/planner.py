from app.llm.llm_client import LLMClient
from app.utils.prompt_builder import build_prompt
import threading

_llm = None
_lock = threading.Lock()


def _get_llm():
    global _llm
    if _llm is None:
        with _lock:
            if _llm is None:
                _llm = LLMClient()
    return _llm


def run_planner(prompt, skill="planner/build_roadmap.md", agent_name="planner"):
    llm = _get_llm()
    full_prompt = build_prompt(agent_name, skill, prompt)

    return llm.generate(
        full_prompt,
        agent_name=agent_name,
        metadata={"skill": skill, "type": "planner"}
    )
