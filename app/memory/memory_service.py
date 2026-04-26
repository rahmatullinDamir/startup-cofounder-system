import asyncio
import threading
import logging
from typing import Any, List
from app.memory.neo4j_client import Neo4jClient
from app.memory.graphiti_rag import GraphitiRAG, get_rag

logger = logging.getLogger(__name__)


class MemoryService:
    _indexing_tasks = set()
    _tasks_lock = threading.Lock()

    def __init__(self):
        self.db = Neo4jClient()
        self.rag = get_rag()
        self._lock = threading.Lock()

    def store_idea(self, idea: Any, create_checkpoint: bool = True) -> str:
        """Сохраняет идею в Neo4j и инициирует фоновую индексацию в Graphiti."""
        content = str(idea)
        result = self.db.query("""
            CREATE (i:Idea {content: $content, timestamp: timestamp()})
            RETURN elementId(i) as id
        """, {"content": content})

        if not result:
            raise RuntimeError("Failed to store idea in Neo4j")

        idea_id = result[0]["id"]
        if create_checkpoint:
            self.store_checkpoint(idea_id, content)

        self._index_with_graphiti(content)
        return idea_id

    def _index_with_graphiti(self, content: str):
        """Фоновая индексация через GraphitiRAG."""
        try:
            # Вызываем метод обертки, который управляет потоками
            self.rag.index_document(text=content, metadata={"source": "memory_service_idea"})
            logger.debug("Graphiti indexing triggered")
        except Exception as e:
            logger.warning(f"Graphiti indexing failed: {e}")

    def store_plan(self, idea_id: str, plan: Any):
        """Сохраняет план реализации и связывает его с идеей (Исправляет ошибку Planner)."""
        content = str(plan)
        try:
            self.db.query("""
                MATCH (i:Idea) WHERE elementId(i) = $idea_id
                CREATE (p:Plan {content: $content, timestamp: timestamp()})
                CREATE (i)-[:HAS_PLAN]->(p)
            """, {"idea_id": idea_id, "content": content})
            logger.info(f"Plan stored for idea {idea_id}")
        except Exception as e:
            logger.error(f"Failed to store plan: {e}")

    def get_best_ideas(self, limit: int = 5) -> List[dict]:
        """Возвращает идеи с лучшим скором для инструментов агентов."""
        try:
            return self.db.query("""
                MATCH (i:Idea)-[:HAS_EVAL]->(e:Evaluation)
                RETURN i.content as content, e.score as score, elementId(i) as id
                ORDER BY e.score DESC LIMIT $limit
            """, {"limit": limit}) or []
        except Exception as e:
            logger.error(f"Error getting best ideas: {e}")
            return []

    def store_evaluation(self, idea_id: str, evaluation: dict):
        self.db.query("""
            MATCH (i:Idea) WHERE elementId(i) = $id
            CREATE (e:Evaluation {content: $eval, score: $score, timestamp: timestamp()})
            CREATE (i)-[:HAS_EVAL]->(e)
        """, {
            "id": idea_id,
            "eval": str(evaluation),
            "score": evaluation.get("final_score", 0)
        })

    def link_iteration(self, old_id: str, new_id: str, reason: str):
        self.db.query("""
            MATCH (a:Idea), (b:Idea) WHERE elementId(a) = $old AND elementId(b) = $new
            CREATE (a)-[:ITERATED_TO {reason: $reason}]->(b)
        """, {"old": old_id, "new": new_id, "reason": reason})

    def get_rag_context(self, agent_name: str, user_input: str) -> str:
        return self.rag.get_context_for_agent(agent_name, user_input) if self.rag else ""

    def store_checkpoint(self, idea_id: str, content: str):
        with self._lock:
            self.db.query("""
                MATCH (i:Idea) WHERE elementId(i) = $id
                CREATE (c:Checkpoint {content: $content, timestamp: timestamp()})
                CREATE (i)-[:HAS_CHECKPOINT]->(c)
            """, {"id": idea_id, "content": content})

    def close(self):
        self.db.close()
        if hasattr(self.rag, "close"): self.rag.close()
