import os
from langfuse import Langfuse


class LangfuseClient:

    def __init__(self):
        self.client = Langfuse(
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", "xxx"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "xxx"),
            host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000")
        )

    def create_trace(self, name, input=None, output=None, metadata=None):
        """Создаёт trace (через start_observation, который автоматически создаёт trace)."""
        return self.client.start_observation(
            name=name,
            input=input,
            output=output,
            metadata=metadata or {}
        )

    def trace_agent(self, agent_name, input_data, output_data, meta=None):
        """Устаревший метод для совместимости."""
        self.create_trace(
            name=agent_name,
            input=input_data,
            output=output_data,
            metadata=meta or {}
        )