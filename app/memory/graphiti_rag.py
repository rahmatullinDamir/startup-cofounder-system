import os
import logging
import asyncio
import threading
from datetime import datetime
from typing import List, Dict, Any
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

try:
    from graphiti_core import Graphiti
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client import OpenAIClient
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from app.memory.ollama_embedder import OllamaEmbedder
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False

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
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

        if GRAPHITI_AVAILABLE: self._init_graphiti_sync()
        self.db = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=120)

    def _init_graphiti_sync(self):
        async def _setup():
            base_ollama_url = self.llm_url.replace('/api/generate', '/v1')

            config = LLMConfig(
                api_key="ollama",
                model=self.model,
                base_url=base_ollama_url,
                temperature=0.1
            )

            llm = OpenAIClient(config=config)

            embedder_url = self.llm_url.replace('/api/generate', '')
            embedder = OllamaEmbedder(model=self.embed_model, base_url=embedder_url)


            engine = Graphiti(
                uri=self.uri,
                user=self.user,
                password=self.password,
                llm_client=llm,
                embedder=embedder,
                # Убираем cross_encoder или ставим его в None,
                # чтобы он не дергал gpt-4.1-nano
                cross_encoder=None,
                graph_driver=Neo4jDriver(uri=self.uri, user=self.user, password=self.password)
            )

            try:
                await engine.bootstrap()
                logger.info("Graphiti schema bootstrapped successfully")
            except Exception as e:
                logger.error(f"Bootstrap failed: {e}")

            return engine

    async def add_episode(self, content: str, **kwargs):
        """Прослойка для совместимости."""
        if not self.engine: return
        return await self.engine.add_episode(
            name=kwargs.get('name', f"ep_{datetime.utcnow().timestamp()}"),
            episode_body=content,
            source_description=kwargs.get('source', 'memory'),
            reference_time=datetime.utcnow().isoformat()
        )

    def index_document(self, text: str, metadata: Dict[str, Any] = None):
        if not self.engine: return
        source = metadata.get('source', 'unknown') if metadata else 'unknown'
        self._run_async(self.add_episode(content=text, source=source))

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.engine: return []
        async def _search():
            res = await self.engine.search(query, num_results=top_k)
            return [{"content": r.get("content", ""), "metadata": r.get("metadata", {})} for r in res]
        return self._run_async(_search())

    def get_context_for_agent(self, agent_name: str, user_input: str) -> str:
        results = self.search(user_input, top_k=3)
        return "".join([f"\n- {r['content']}" for r in results])

    def close(self):
        if self._loop.is_running(): self._loop.call_soon_threadsafe(self._loop.stop)
        if self.db: self.db.close()

_rag_instance = None
def get_rag() -> GraphitiRAG:
    global _rag_instance
    if _rag_instance is None: _rag_instance = GraphitiRAG()
    return _rag_instance