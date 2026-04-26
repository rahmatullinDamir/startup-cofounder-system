import os
from langfuse import Langfuse


class LangfuseClient:

    def __init__(self):

        self.client = Langfuse(
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", "xxx"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "xxx"),
            host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000")
        )

    def trace_agent(self, agent_name, input_data, output_data, meta=None):

        self.client.trace(
            name=agent_name,
            input=input_data,
            output=output_data,
            metadata=meta or {}
        )