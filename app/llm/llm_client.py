import requests
import json
import time
import re
from langfuse import Langfuse


class LLMClient:

    def __init__(self):
        self.model = "qwen:4b"
        self.url = "http://host.docker.internal:11434/api/generate"
        self.lf = Langfuse()

    def generate(self, prompt, agent_name="agent", metadata=None):

        trace = self.lf.trace(name=agent_name)

        start = time.time()

        try:
            raw = self._invoke(prompt)
            parsed = self._parse(raw)

            trace.span(
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
                "error": str(e)
            })

            return {"error": str(e)}

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
                    timeout=60
                )

                return r.json()["response"]

            except Exception as e:
                last_error = e
                time.sleep(i + 1)

        raise Exception(f"LLM failed: {last_error}")

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