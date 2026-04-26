from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import threading
import logging
import uvicorn

from app.core.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent API", version="1.0.0")

_orchestrator = None
_lock = threading.Lock()


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        with _lock:
            if _orchestrator is None:
                _orchestrator = Orchestrator()
    return _orchestrator


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000, description="User request for idea generation")
    use_tools: bool = Field(default=True, description="Whether to use tools for context enrichment")


class GenerateResponse(BaseModel):
    idea: Optional[dict] = None
    critique: Optional[dict] = None
    plan: Optional[dict] = None
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "multi-agent"}


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    try:
        orchestrator = get_orchestrator()
        result = orchestrator.run(request.prompt)
        
        if result is None:
            raise HTTPException(status_code=500, detail="Orchestrator returned None")
        
        if isinstance(result, dict):
            return GenerateResponse(
                idea=result.get("idea"),
                critique=result.get("critique"),
                plan=result.get("plan")
            )
        
        raise HTTPException(status_code=500, detail=f"Unexpected result type: {type(result)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown - закрываем соединение с Neo4j."""
    global _orchestrator
    if _orchestrator:
        logger.info("Shutting down - closing Neo4j connection")
        _orchestrator.memory.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
