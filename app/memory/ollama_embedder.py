import os
import logging
import httpx
from typing import List
from graphiti_core.embedder import EmbedderClient

logger = logging.getLogger(__name__)


class OllamaEmbedder(EmbedderClient):
    """Кастомный embedder для Ollama с использованием /api/embeddings endpoint."""
    
    def __init__(self, model: str = "all-minilm", base_url: str = "http://ollama:11434"):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"OllamaEmbedder initialized with model {model} at {self.base_url}")
    
    async def create(self, input_data: List[str]) -> List[List[float]]:
        """Создаёт embeddings для списка текстов."""
        embeddings = []
        for text in input_data:
            try:
                response = await self._client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
            except Exception as e:
                logger.error(f"Embedding failed for text: {e}")
                raise
        return embeddings
    
    async def create_batch(self, input_data: List[str]) -> List[List[float]]:
        """Batch embeddings (по умолчанию вызывает create)."""
        return await self.create(input_data)
    
    async def close(self):
        await self._client.aclose()
