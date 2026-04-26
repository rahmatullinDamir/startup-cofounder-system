"""
Tools - инструменты для агентов.
"""

from typing import Callable, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Реестр инструментов."""

    def __init__(self, memory_service=None, rag=None):
        self.tools: Dict[str, callable] = {}
        self.memory = memory_service
        self.rag = rag
        self._register_default_tools()

    def _register_default_tools(self):
        """Регистрация инструментов по умолчанию."""
        # Поиск в графе
        self.tools["graph_search"] = self.graph_search
        self.tools["similar_ideas"] = self.similar_ideas
        self.tools["best_ideas"] = self.best_ideas
        self.tools["failure_patterns"] = self.failure_patterns
        self.tools["rag_context"] = self.rag_context

    def graph_search(self, query: str, top_k: int = 3) -> List[str]:
        """Поиск в графе знаний."""
        if not self.memory:
            return []
        try:
            results = self.memory.db.query("""
                MATCH (i:Idea)
                WHERE toLower(i.content) CONTAINS toLower($query)
                RETURN i.content as content
                LIMIT $top_k
            """, {"query": query, "top_k": top_k})
            return [r["content"] for r in results]
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []

    def similar_ideas(self, problem: str, top_k: int = 3) -> List[Dict]:
        """Найти идеи с похожей проблемой."""
        if not self.memory:
            return []
        try:
            results = self.memory.db.query("""
                MATCH (i:Idea)
                WHERE toLower(i.content) CONTAINS toLower($problem)
                RETURN i.content as content
                LIMIT $top_k
            """, {"problem": problem, "top_k": top_k})
            return [{"content": r["content"]} for r in results]
        except Exception as e:
            logger.error(f"Similar ideas search failed: {e}")
            return []

    def best_ideas(self, min_score: int = 7, top_k: int = 5) -> List[Dict]:
        """Получить лучшие идеи."""
        if not self.memory:
            return []
        try:
            results = self.memory.get_best_ideas()
            return results[:top_k]
        except Exception as e:
            logger.error(f"Best ideas retrieval failed: {e}")
            return []

    def failure_patterns(self) -> List[Dict]:
        """Получить причины неудач."""
        if not self.memory:
            return []
        try:
            return self.memory.get_similar_failures()
        except Exception as e:
            logger.error(f"Failure patterns failed: {e}")
            return []

    def rag_context(self, agent_name: str, query: str) -> str:
        """Получить контекст из RAG."""
        if not self.rag:
            return ""
        try:
            return self.rag.get_context_for_agent(agent_name, query)
        except Exception as e:
            logger.error(f"RAG context failed: {e}")
            return ""

    def execute(self, tool_name: str, **kwargs) -> Any:
        """Выполнить инструмент."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool not found: {tool_name}"}
        try:
            return tool(**kwargs)
        except Exception as e:
            return {"error": str(e)}

    def list_tools(self) -> List[Dict]:
        """Список доступных инструментов."""
        return [
            {"name": name, "description": self._get_description(name)}
            for name in self.tools.keys()
        ]

    def _get_description(self, name: str) -> str:
        """Описание инструмента."""
        descs = {
            "graph_search": "Поиск в графе знаний",
            "similar_ideas": "Поиск похожих идей",
            "best_ideas": "Лучшие идеи (score >= 7)",
            "failure_patterns": "Паттерны неудач",
            "rag_context": "Контекст из RAG"
        }
        return descs.get(name, "Нет описания")
