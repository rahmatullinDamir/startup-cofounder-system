import asyncio
import logging
from app.memory.graphiti_rag import GraphitiRAG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def index_souls():
    logger.info("Starting SOUL files indexing...")
    
    rag = GraphitiRAG()
    
    try:
        await rag.index_soul_files()
        logger.info("SOUL files indexing completed")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
    finally:
        rag.close()


if __name__ == "__main__":
    asyncio.run(index_souls())
