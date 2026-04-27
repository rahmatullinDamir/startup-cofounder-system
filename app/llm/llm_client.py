import requests
import json
import time
import re
import os
import logging
from app.observability.langfuse_client import LangfuseClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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

            # Валидация: проверяем, что ответ не пустой и содержит JSON
            if not self._validate_response(parsed, raw):
                raise ValueError(f"Invalid response: empty or non-JSON content")

            trace.start_observation(
                name="llm_call",
                input={"prompt": prompt[:2000]},
                output={"response": raw[:2000]}
            )

            trace.update(metadata={
                "latency": time.time() - start,
                "status": "ok",
                "response_length": len(raw),
                **(metadata or {})
            })

            logger.info(f"✅ Valid response received ({len(raw)} chars)")
            return parsed

        except Exception as e:
            logger.error(f"❌ LLM error: {e}")
            trace.update(metadata={
                "status": "error",
                "error": str(e),
                "agent": agent_name
            })
            return {"error": str(e), "raw": str(e)}

    def _validate_response(self, parsed, raw):
        """Проверяет, что ответ содержит валидный JSON с ключевыми полями."""
        if not raw or len(raw.strip()) == 0:
            logger.error("❌ Empty response from LLM")
            return False
        
        if isinstance(parsed, dict) and "error" in parsed:
            logger.error(f"❌ Response contains error: {parsed.get('error')}")
            return False
        
        # Проверяем наличие хотя бы одного ключа (не только "raw")
        if isinstance(parsed, dict) and len(parsed) > 0 and "raw" not in parsed:
            return True
        
        if isinstance(parsed, dict) and "raw" in parsed and len(parsed) == 1:
            logger.error("❌ Response is raw text, not valid JSON")
            return False
        
        return True

    def _invoke(self, prompt, retries=3):
        last_error = None

        for i in range(retries):
            try:
                logger.info(f"📤 LLM request attempt {i+1}/{retries} to {self.url} with model {self.model}")
                logger.debug(f"Prompt preview: {prompt[:300]}...")
                
                r = requests.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": 512,
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    },
                    timeout=300
                )

                logger.info(f"📥 Response status: {r.status_code}")

                if r.status_code != 200:
                    logger.error(f"❌ HTTP error: {r.status_code} - {r.text[:500]}")
                    raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")

                data = r.json()

                if "response" not in data:
                    logger.error(f"❌ Invalid response format: {data}")
                    raise Exception(f"Invalid response format: {data}")

                response_text = data["response"]
                logger.info(f"📝 Raw response length: {len(response_text)} chars")
                
                if len(response_text.strip()) == 0:
                    logger.warning("⚠️ Empty response, retrying...")
                    last_error = ValueError("Empty response")
                    time.sleep(i + 1)
                    continue

                return response_text

            except requests.exceptions.Timeout:
                logger.error(f"⏱️ Timeout on attempt {i+1}")
                last_error = TimeoutError("Request timed out")
                time.sleep(i + 1)
            except Exception as e:
                logger.error(f"⚠️ Error on attempt {i+1}: {e}")
                last_error = e
                time.sleep(i + 1)

        logger.error(f"❌ LLM failed after {retries} retries: {last_error}")
        raise Exception(f"LLM failed after {retries} retries: {last_error}")

    def _parse(self, text):
        """Пытается распарсить JSON из ответа."""
        if not text or len(text.strip()) == 0:
            return {}
        
        text = text.strip()
        
        # Прямой парсинг
        try:
            result = json.loads(text)
            logger.debug("✅ Direct JSON parse successful")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"Direct parse failed: {e}")
            pass

        # Поиск JSON в тексте
        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                result = json.loads(match.group())
                logger.debug("✅ JSON extracted from text")
                return result
            except json.JSONDecodeError as e:
                logger.debug(f"Extracted JSON parse failed: {e}")
                pass

        logger.warning("⚠️ Could not parse JSON, returning raw text")
        return {"raw": text}
