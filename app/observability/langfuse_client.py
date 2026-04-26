import os
import logging
from typing import Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FakeTrace:
    """Заглушка для Langfuse при недоступности."""
    _counter = 0
    
    def __init__(self):
        FakeTrace._counter += 1
        self.trace_id = f"fake-trace-id-{FakeTrace._counter}"
    
    def update(self, **kwargs):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeSpan:
    """Заглушка для Langfuse span."""
    def update(self, **kwargs):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class LangfuseClient:

    def __init__(self):
        try:
            from langfuse import Langfuse
            self.client = Langfuse(
                secret_key=os.getenv("LANGFUSE_SECRET_KEY", "xxx"),
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "xxx"),
                host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000")
            )
            self._available = True
            logger.info("Langfuse client initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available: {e}")
            self.client = None
            self._available = False

    def create_trace(self, name, input=None, output=None, metadata=None):
        """Создаёт trace с graceful fallback при недоступности Langfuse."""
        if not self._available or not self.client:
            return FakeTrace()
        
        try:
            trace = self.client.trace(
                name=name,
                input=input,
                output=output,
                metadata=metadata or {}
            )
            return trace
        except Exception as e:
            logger.warning(f"Langfuse trace failed: {e}")
            return FakeTrace()

    def create_span(self, name, input=None, output=None, metadata=None, trace_id=None):
        """Создаёт span внутри trace."""
        if not self._available or not self.client:
            return FakeSpan()
        
        try:
            # Если trace_id не передан, создаём заглушку
            if trace_id is None:
                return FakeSpan()
            
            span = self.client.span(
                name=name,
                input=input,
                output=output,
                metadata=metadata or {},
                trace_id=trace_id
            )
            return span
        except Exception as e:
            logger.warning(f"Langfuse span failed: {e}")
            return FakeSpan()

    def create_score(self, trace_id, name, value, metadata=None):
        """Создаёт score для trace."""
        if not self._available or not self.client:
            return
        
        try:
            self.client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.warning(f"Langfuse score failed: {e}")

    def trace_agent(self, agent_name, input_data, output_data, meta=None):
        """Устаревший метод для совместимости."""
        return self.create_trace(
            name=agent_name,
            input=input_data,
            output=output_data,
            metadata=meta or {}
        )
