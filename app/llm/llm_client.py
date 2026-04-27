import requests
import json
import time
import re
import os
from app.observability.langfuse_client import LangfuseClient


class LLMClient:

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "qwen3.5:2b")
        self.url = os.getenv("LLM_URL", "http://host.docker.internal:11434/api/generate")
        self.langfuse = LangfuseClient()

    def generate(self, prompt, agent_name="agent", metadata=None):
        trace = self.langfuse.create_trace(name=agent_name)

        start = time.time()

        try:
            raw = self._invoke(prompt)
            parsed = self._parse(raw)

            trace.start_observation(
                name="llm_call",
                input={"prompt": prompt[:2000]},
                output={"response": raw[:2000]}
            )

            trace.update(metadata={
                "latency": time.time() - start,
                "status": "ok",
                **(metadata or {})
            })

            return parsed

        except Exception as e:
            trace.update(metadata={
                "status": "error",
                "error": str(e),
                "agent": agent_name
            })

            return {"error": str(e), "raw": str(e)}

    def _invoke(self, prompt, retries=2):
        last_error = None

        for i in range(retries):
            try:
                r = requests.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=180
                )

                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")

                data = r.json()

                if "response" not in data:
                    raise Exception(f"Invalid response format: {data}")

                return data["response"]

            except Exception as e:
                last_error = e
                time.sleep(i + 1)

        raise Exception(f"LLM failed after {retries} retries: {last_error}")

    def _parse(self, text):
        try:
            return json.loads(text)
        except:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                return json.loads(match.group())
            except:
                pass

        return {"raw": text}
