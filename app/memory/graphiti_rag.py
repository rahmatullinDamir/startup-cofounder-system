import os
import os
import logging
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

try:
    from graphiti_core import Graphiti
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client import OpenAIClient
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    # Импортируем наш кастомный embedder
    from app.memory.ollama_embedder import OllamaEmbedder
    
    GRAPHITI_AVAILABLE = True
except ImportError as e:
    GRAPHITI_AVAILABLE = False
    logger.warning(f"Graphiti not installed: {e}. RAG features will be disabled.")


class GraphitiRAG:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.model = os.getenv("LLM_MODEL", "llama3.2:3b")
        self.llm_url = os.getenv("LLM_URL", "http://ollama:11434/api/generate")
        self.embed_model = os.getenv("EMBED_MODEL", "all-minilm")
        self.engine = None
        self.db = None
        if GRAPHITI_AVAILABLE:
            self._init_graphiti()
        self._init_neo4j()

    def _init_graphiti(self):
        try:
            logger.info("Initializing Graphiti engine...")
            
            # Настройка LLM для Ollama
            llm_config = LLMConfig(
                api_key="ollama",
                model=self.model,
                base_url=f"{self.llm_url}",  # Полный URL без /v1
                temperature=0.7
            )
            
            # Создаем клиент LLM
            llm_client = OpenAIClient(config=llm_config)
            
            # Создаем кастомный OllamaEmbedder
            embedder = OllamaEmbedder(
                model=self.embed_model,
                base_url=self.llm_url.replace('/api/generate', '')
            )
            
            # Настройка граф драйвера
            graph_driver = Neo4jDriver(
                uri=self.uri,
                user=self.user,
                password=self.password
            )
            
            # Настройка reranker для Ollama
            reranker = OpenAIRerankerClient(config=llm_config)
            
            # Graphiti с кастомным embedder
            self.engine = Graphiti(
                uri=self.uri,
                user=self.user,
                password=self.password,
                llm_client=llm_client,
                embedder=embedder,
                graph_driver=graph_driver,
                cross_encoder=reranker
            )
            logger.info("Graphiti engine initialized successfully with OllamaEmbedder")
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            import traceback
            traceback.print_exc()
            self.engine = None

    def _init_neo4j(self):
        self.db = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        logger.info("Neo4j driver initialized")

    async def index_document(self, text: str, metadata: Dict[str, Any] = None):
        if not self.engine:
            logger.warning("Graphiti not available, skipping indexing")
            return
        try:
            source = metadata.get('source', 'unknown') if metadata else 'unknown'
            await self.engine.add_episode(
                episode_body=text,
                source_description=source,
                reference_time=datetime.utcnow().isoformat()
            )
            logger.info(f"Document indexed: {source}")
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            import traceback
            traceback.print_exc()

    async def index_soul_files(self):
        souls_dir = Path(__file__).parent.parent / "souls"
        if not souls_dir.exists():
            logger.warning(f"Souls directory not found: {souls_dir}")
            return
        documents = []
        for soul_file in souls_dir.glob("*.SOUL.md"):
            try:
                content = soul_file.read_text(encoding="utf-8")
                source_name = str(soul_file.name)
                documents.append({
                    "content": content,
                    "source": source_name,
                    "type": "soul",
                    "agent": soul_file.stem.replace(".SOUL", "")
                })
                logger.info(f"Loaded SOUL file: {source_name}")
            except Exception as e:
                logger.error(f"Failed to load {soul_file}: {e}")
        if documents:
            for doc in documents:
                await self.engine.add_episode(
                    episode_body=doc["content"],
                    source_description=doc["source"],
                    reference_time=datetime.utcnow().isoformat()
                )
            logger.info(f"Indexed {len(documents)} SOUL files")

    async def index_idea(self, idea: Dict[str, Any]):
        text = f"Startup Idea: Problem: {idea.get('problem', '')} Solution: {idea.get('solution', '')} Target Audience: {idea.get('target_audience', '')}"
        await self.index_document(text, metadata={"type": "idea", "problem": idea.get("problem", ""), "solution": idea.get("solution", "")})

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.engine:
            logger.warning("Graphiti not available, returning empty results")
            return []
        try:
            results = await self.engine.search(query, num_results=top_k)
            formatted = [
                {"content": r.get("content", ""), "score": r.get("score", 0), "metadata": r.get("metadata", {})} for r
                in results]
            logger.info(f"Search returned {len(formatted)} results")
            return formatted
        except Exception as e:
            logger.error(f"Search failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def search_sync(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.new_event_loop().run_until_complete(self.search(query, top_k)))
                return future.result()
        except RuntimeError:
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
            if _rag_instance is None:
                _rag_instance = GraphitiRAG()
    return _rag_instance
