import asyncio
import threading
import logging
from app.memory.neo4j_client import Neo4jClient
from app.memory.graphiti_rag import GraphitiRAG, get_rag

logger = logging.getLogger(__name__)


class MemoryService:
    _indexing_tasks = []  # Хранение задач для предотвращения garbage collection
    _tasks_lock = threading.Lock()

    def __init__(self):
        self.db = Neo4jClient()
        self.rag = get_rag()
        self._lock = threading.Lock()  # Thread safety для критических операций

    def store_idea(self, idea, create_checkpoint=True):
        """
        Сохраняет идею и создаёт checkpoint для rollback.
        """
        result = self.db.query("""
            CREATE (i:Idea {content: $idea})
            RETURN elementId(i) as id
        """, {"idea": str(idea)})

        idea_id = result[0]["id"]
        
        # Создаём checkpoint для возможности rollback
        if create_checkpoint:
            self.store_checkpoint(idea_id, idea)
        
        # Асинхронная индексация в фоне (fire-and-forget)
        self._index_idea_async(idea)
        
        return idea_id

    def _index_idea_async(self, idea):
        """Асинхронная индексация без блокировки основного потока."""
        try:
            # Используем create_task или новый loop для совместимости с Python 3.10+
            try:
                # Пытаемся получить текущий запущенный loop
                loop = asyncio.get_running_loop()
                # Если loop запущен, создаём задачу для выполнения в фоне
                task = asyncio.create_task(self.rag.index_idea(idea))
                # Сохраняем задачу, чтобы предотвратить garbage collection
                with MemoryService._tasks_lock:
                    MemoryService._indexing_tasks.append(task)
                    # Удаляем завершённые задачи
                    MemoryService._indexing_tasks = [
                        t for t in MemoryService._indexing_tasks 
                        if not t.done()
                    ]
                logger.debug("RAG indexing scheduled as background task")
            except RuntimeError:
                # Нет запущенного loop - создаём новый и выполняем синхронно
                # Это fire-and-forget, поэтому не блокируем основную операцию
                new_loop = asyncio.new_event_loop()
                try:
                    new_loop.run_until_complete(self.rag.index_idea(idea))
                finally:
                    new_loop.close()
        except Exception as e:
            # Логирование ошибки, но не блокируем основную операцию
            logger.warning(f"RAG indexing failed (non-critical): {e}")

    def store_evaluation(self, idea_id, evaluation):
        """Сохраняет оценку идеи."""
        self.db.query("""
            MATCH (i:Idea) WHERE elementId(i) = $id
            CREATE (e:Evaluation {content: $eval, score: $score})
            CREATE (i)-[:HAS_EVAL]->(e)
        """, {
            "id": idea_id,
            "eval": str(evaluation),
            "score": evaluation.get("final_score", 0)
        })

    def store_plan(self, idea_id, plan):
        """Сохраняет план (roadmap) для идеи."""
        self.db.query("""
            MATCH (i:Idea) WHERE elementId(i) = $id
            CREATE (p:Plan {content: $plan})
            CREATE (i)-[:HAS_PLAN]->(p)
        """, {
            "id": idea_id,
            "plan": str(plan)
        })

    def link_iteration(self, old_id, new_id, reason):
        """Связывает идеи в цепочку итераций."""
        self.db.query("""
            MATCH (a:Idea), (b:Idea)
            WHERE elementId(a) = $old AND elementId(b) = $new
            CREATE (a)-[:ITERATED_TO {reason: $reason}]->(b)
        """, {
            "old": old_id,
            "new": new_id,
            "reason": reason
        })

    def store_failure(self, idea_id, reason):
        """Сохраняет причину неудачи."""
        self.db.query("""
            MATCH (i:Idea) WHERE elementId(i) = $id
            CREATE (f:Failure {reason: $reason})
            CREATE (i)-[:FAILED]->(f)
        """, {
            "id": idea_id,
            "reason": reason
        })

    def get_similar_failures(self):
        """Получает похожие неудачи для анализа паттернов."""
        result = self.db.query("""
            MATCH (i:Idea)-[:FAILED]->(f)
            RETURN i.content as idea, f.reason as reason
            LIMIT 5
        """)
        return result

    def get_best_ideas(self):
        """Получает лучшие идеи (score >= 7)."""
        result = self.db.query("""
            MATCH (i:Idea)-[:HAS_EVAL]->(e)
            WHERE e.score >= 7
            RETURN i.content as idea, e.score as score
            ORDER BY e.score DESC
            LIMIT 3
        """)
        return result

    def get_last_good_idea(self):
        """Получает последнюю хорошую идею."""
        result = self.db.query("""
            MATCH (i:Idea)-[:HAS_EVAL]->(e)
            WHERE e.score >= 7
            RETURN i.content as idea
            ORDER BY e.score DESC
            LIMIT 1
        """)
        return result[0]["idea"] if result else None

    def get_rag_context(self, agent_name: str, user_input: str) -> str:
        """Получает контекст из RAG для агента."""
        if self.rag:
            return self.rag.get_context_for_agent(agent_name, user_input)
        return ""

    def store_checkpoint(self, idea_id, idea_content):
        """
        Создаёт checkpoint для идеи - точка восстановления при self-healing.
        """
        with self._lock:  # Thread-safe
            self.db.query("""
                MATCH (i:Idea) WHERE elementId(i) = $id
                CREATE (c:Checkpoint {content: $content, timestamp: timestamp()})
                CREATE (i)-[:HAS_CHECKPOINT]->(c)
            """, {
                "id": idea_id,
                "content": str(idea_content)
            })

    def rollback(self):
        """
        Возвращается к последнему checkpoint для восстановления состояния.
        """
        with self._lock:  # Thread-safe
            result = self.db.query("""
                MATCH (i:Idea)-[:HAS_CHECKPOINT]->(c)
                RETURN i.content as idea, elementId(i) as id
                ORDER BY c.timestamp DESC
                LIMIT 1
            """)

            if not result:
                return None

            return {
                "idea": result[0]["idea"],
                "idea_id": result[0]["id"]
            }

    def close(self):
        """Корректное закрытие соединений."""
        self.db.close()
        if hasattr(self.rag, "close"):
            self.rag.close()
