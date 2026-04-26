import os
import logging
import asyncio
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

try:
    from graphiti import Graphiti

    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    logger.warning("Graphiti not installed. RAG features will be disabled.")


class GraphitiRAG:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.model = os.getenv("LLM_MODEL", "llama3.2:3b")
        self.llm_url = os.getenv("LLM_URL", "http://localhost:11434/api/generate")
        self.engine = None
        self.db = None
        if GRAPHITI_AVAILABLE:
            self._init_graphiti()
        self._init_neo4j()

    def _init_graphiti(self):
        try:
            logger.info("Initializing Graphiti engine...")
            self.engine = Graphiti(
                llm_config={"model": self.model, "base_url": self.llm_url},
                graph_config={"neo4j_uri": self.uri, "neo4j_user": self.user, "neo4j_password": self.password}
            )
            logger.info("Graphiti engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            self.engine = None

    def _init_neo4j(self):
        self.db = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        logger.info("Neo4j driver initialized")

    async def index_document(self, text: str, metadata: Dict[str, Any] = None):
        if not self.engine:
            logger.warning("Graphiti not available, skipping indexing")
            return
        try:
            await self.engine.process(text, metadata=metadata or {})
            logger.info(f"Document indexed: {metadata.get('source', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to index document: {e}")

    async def index_soul_files(self):
        souls_dir = Path(__file__).parent.parent / "souls"
        if not souls_dir.exists():
            logger.warning(f"Souls directory not found: {souls_dir}")
            return
        for soul_file in souls_dir.glob("*.SOUL.md"):
            try:
                content = soul_file.read_text(encoding="utf-8")
                await self.index_document(content, metadata={"source": str(soul_file.name), "type": "soul",
                                                             "agent": soul_file.stem.replace(".SOUL", "")})
                logger.info(f"Indexed SOUL file: {soul_file.name}")
            except Exception as e:
                logger.error(f"Failed to index {soul_file}: {e}")

    async def index_idea(self, idea: Dict[str, Any]):
        text = f"Startup Idea: Problem: {idea.get('problem', '')} Solution: {idea.get('solution', '')} Target Audience: {idea.get('target_audience', '')}"
        await self.index_document(text, metadata={"type": "idea", "problem": idea.get("problem", ""),
                                                  "solution": idea.get("solution", "")})

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.engine:
            logger.warning("Graphiti not available, returning empty results")
            return []
        try:
            results = await self.engine.search(query, top_k=top_k)
            formatted = [
                {"content": r.get("content", ""), "score": r.get("score", 0), "metadata": r.get("metadata", {})} for r
                in results]
            logger.info(f"Search returned {len(formatted)} results")
            return formatted
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def search_sync(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Синхронный поиск с корректной обработкой event loop в многопоточной среде.
        Создаёт новый loop для каждого вызова, чтобы избежать конфликтов.
        """
        try:
            # Проверяем, есть ли уже запущенный loop в текущем потоке
            loop = asyncio.get_running_loop()
            # Если loop уже запущен, используем run_coroutine_threadsafe
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.new_event_loop().run_until_complete(self.search(query, top_k)))
                return future.result()
        except RuntimeError:
            # Нет запущенного loop - можем создать и запустить новый
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.search(query, top_k))
            finally:
                loop.close()

    def get_context_for_agent(self, agent_name: str, user_input: str) -> str:
        results = self.search_sync(user_input, top_k=3)
        if not results:
            return ""
        context_parts = []
        for i, result in enumerate(results, 1):
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            source = metadata.get("source", "unknown")
            score = result.get("score", 0)
            context_parts.append(f"\n--- Context {i} (source: {source}, score: {score:.2f}) ---\n{content}\n")
        return "\n".join(context_parts)

    def get_similar_ideas(self, problem_description: str, top_k: int = 3) -> List[str]:
        try:
            with self.db.session() as session:
                result = session.run(
                    "MATCH (i:Idea) WHERE i.content CONTAINS $problem RETURN i.content as content LIMIT $top_k",
                    {"problem": problem_description, "top_k": top_k})
                return [record["content"] for record in result]
        except Exception as e:
            logger.error(f"Failed to find similar ideas: {e}")
            return []

    def close(self):
        if self.db:
            self.db.close()
            logger.info("Neo4j connection closed")


_rag_instance = None
_rag_lock = threading.Lock()


def get_rag() -> GraphitiRAG:
    global _rag_instance
    if _rag_instance is None:
        with _rag_lock:
            # Double-check locking pattern
            if _rag_instance is None:
                _rag_instance = GraphitiRAG()
    return _rag_instance
