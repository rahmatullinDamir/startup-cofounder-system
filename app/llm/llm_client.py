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
        self.model = os.getenv("LLM_MODEL", "Ministral-3:3B")
        self.url = os.getenv("LLM_URL", "http://host.docker.internal:11434/api/generate")
        self.langfuse = LangfuseClient()

    def generate(self, prompt, agent_name="agent", metadata=None):
        trace = self.langfuse.create_trace(name=agent_name)

        start = time.time()

        try:
            raw = self._invoke(prompt)
            parsed = self._parse(raw)

            if not self._validate_response(parsed, raw):
                raise ValueError(f"Invalid response: empty content")

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

            logger.info(f"Valid response received ({len(raw)} chars)")
            return parsed

        except Exception as e:
            logger.error(f"LLM error: {e}")
            trace.update(metadata={
                "status": "error",
                "error": str(e),
                "agent": agent_name
            })
            return {"error": str(e), "raw": str(e)}

    def _validate_response(self, parsed, raw):
        if not raw or len(raw.strip()) == 0:
            logger.error("Empty response from LLM")
            return False
        if isinstance(parsed, dict) and "error" in parsed:
            logger.error(f"Response contains error: {parsed.get('error')}")
            return False
        return True

    def _invoke(self, prompt, retries=3):
        last_error = None

        for i in range(retries):
            try:
                logger.info(f"LLM request attempt {i+1}/{retries} to {self.url} with model {self.model}")
                
                r = requests.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": 512, "temperature": 0.7, "top_p": 0.9}
                    },
                    timeout=300
                )

                logger.info(f"Response status: {r.status_code}")

                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")

                data = r.json()

                if "response" not in data:
                    raise Exception(f"Invalid response format: {data}")

                response_text = data["response"]
                logger.info(f"Raw response length: {len(response_text)} chars")
                
                if len(response_text.strip()) == 0:
                    logger.warning("Empty response, retrying...")
                    last_error = ValueError("Empty response")
                    time.sleep(i + 1)
                    continue

                return response_text

            except requests.exceptions.Timeout:
                logger.error(f"Timeout on attempt {i+1}")
                last_error = TimeoutError("Request timed out")
                time.sleep(i + 1)
            except Exception as e:
                logger.error(f"Error on attempt {i+1}: {e}")
                last_error = e
                time.sleep(i + 1)

        raise Exception(f"LLM failed after {retries} retries: {last_error}")

    def _parse(self, text):
        if not text or len(text.strip()) == 0:
            return {}
        
        text = text.strip()
        
        # Убираем возможные артефакты (например, /no_think)
        text = re.sub(r"/\s*no_think\s*$", "", text, flags=re.IGNORECASE).strip()

        try:
            result = json.loads(text)
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except json.JSONDecodeError:
            pass

        # Пытаемся найти JSON в тексте
        match = re.search(r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}", text, re.DOTALL)
        if match:
            json_str = match.group()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # Если не удалось, пробуем исправить неэкранированные переносы строк в строках
            try:
                # Заменяем реальные переносы строк внутри строк на \n
                cleaned = re.sub(r'"([^"\\]*(\\.[^"\\]*)*)\n([^"\\]*(\\.[^"\\]*)*)"', 
                                lambda m: m.group(0).replace('\n', '\\n'), json_str)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            # Ещё одна попытка: нормализуем все переносы строк внутри JSON
            try:
                # Разбиваем на строки, убираем лишние переносы внутри строк
                lines = json_str.split('\n')
                normalized_lines = []
                in_string = False
                current_line = ""
                
                for line in lines:
                    if not in_string:
                        current_line = line
                    else:
                        current_line += " " + line.strip()
                    
                    # Считаем кавычки, чтобы определить, внутри строки мы или нет
                    quote_count = current_line.count('"') - current_line.count('\\"')
                    in_string = (quote_count % 2) == 1
                    normalized_lines.append(current_line)
                    
                    if not in_string:
                        normalized_lines.append("\n")
                
                normalized = "".join(normalized_lines).strip()
                # Убираем лишние переносы строк между элементами JSON
                normalized = re.sub(r'\}\s*\n\s*\{', '}\n{', normalized)
                normalized = re.sub(r'\[\s*\n\s*', '[', normalized)
                normalized = re.sub(r'\s*\n\s*\]', ']', normalized)
                
                return json.loads(normalized)
            except json.JSONDecodeError:
                pass

        return {"raw": text, "error": "Failed to parse JSON"}