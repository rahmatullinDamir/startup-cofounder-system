from app.llm.llm_client import LLMClient
from app.utils.prompt_builder import build_prompt
from app.memory.memory_service import MemoryService
from app.tools.tool_registry import ToolRegistry
import threading

_llm = None
_memory = None
_tools = None  # Инициализируется через set_tools()
_llm_lock = threading.Lock()
_memory_lock = threading.Lock()
_tools_lock = threading.Lock()


def _get_llm():
    global _llm
    if _llm is None:
        with _llm_lock:
            if _llm is None:
                _llm = LLMClient()
    return _llm


def _get_memory():
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                _memory = MemoryService()
    return _memory


def set_tools(tools: ToolRegistry):
    """Устанавливает инструменты для ideation agent."""
    global _tools
    with _tools_lock:
        _tools = tools


def run_ideation(prompt, skill="ideation/generate_idea.md", agent_name="ideation", use_tools=True):
    llm = _get_llm()
    memory = _get_memory()
    
    # Читаем _tools с lock
    with _tools_lock:
        current_tools = _tools
    
    context_parts = []
    
    # 1. Контекст из Graphiti RAG
    rag_context = memory.get_rag_context(agent_name, prompt)
    if rag_context:
        context_parts.append(f"[RELEVANT CONTEXT FROM KNOWLEDGE GRAPH]\n{rag_context}")
    
    # 2. Поиск похожих идей (если включены инструменты)
    if use_tools and current_tools:
        similar = current_tools.execute("similar_ideas", problem=prompt, top_k=2)
        if similar:
            context_parts.append(f"[SIMILAR IDEAS FROM GRAPH]\n{similar}")
        
        best = current_tools.execute("best_ideas", min_score=7, top_k=2)
        if best:
            context_parts.append(f"[BEST IDEAS (score >= 7)]\n{best}")
    
    full_prompt = build_prompt(agent_name, skill, prompt)
    
    if context_parts:
        full_prompt += "\n\n" + "\n\n".join(context_parts)
        full_prompt += "\n\nUse the context above to generate a unique, improved idea."
    
    result = llm.generate(
        full_prompt,
        agent_name=agent_name,
        metadata={
            "skill": skill, 
            "type": "ideation", 
            "rag_used": bool(rag_context),
            "tools_used": use_tools and current_tools is not None
        }
    )
    
    return result
