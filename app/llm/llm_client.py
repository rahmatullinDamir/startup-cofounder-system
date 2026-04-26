import requests
import json
import time
import re
import os
import logging
from pathlib import Path
from app.observability.langfuse_client import get_langfuse_client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LLMClient:
    def __init__(self):
        # Модель берем из окружения
        self.model = os.getenv('LLM_MODEL', 'llama3.2:3b')
        # URL по умолчанию меняем на имя сервиса в docker-сети
        self.url = os.getenv('LLM_URL', 'http://ollama:11434/api/generate')
        self.timeout = int(os.getenv('LLM_TIMEOUT', '180'))
        self._ensure_log_dir()

    @property
    def langfuse(self):
        return get_langfuse_client()

    def _ensure_log_dir(self):
        # Создаем путь относительно корня проекта
        self.log_dir = Path(__file__).parent.parent.parent / 'llm_logs'
        self.log_dir.mkdir(exist_ok=True)

    def generate(self, prompt, agent_name='agent', metadata=None):
        trace = self.langfuse.create_trace(name=agent_name)
        start = time.time()

        try:
            raw = self._invoke(prompt)
            self._log_raw_response(agent_name, prompt, raw)
            parsed = self._parse(raw)

            if not self._validate_response(parsed, raw):
                raise ValueError('Invalid response: empty content')

            self.langfuse.create_span(
                name='llm_call',
                input={'prompt': prompt[:2000]},
                output={'response': raw[:2000]},
                trace_id=trace.trace_id if hasattr(trace, 'trace_id') else None
            )

            trace.update(metadata={
                'latency': time.time() - start,
                'status': 'ok',
                'response_length': len(raw),
                **(metadata or {})
            })

            logger.info(f'Valid response received ({len(raw)} chars)')
            return parsed

        except Exception as e:
            logger.error(f'LLM error: {e}')
            trace.update(metadata={
                'status': 'error',
                'error': str(e),
                'agent': agent_name
            })
            return {'error': str(e), 'raw': str(e)}

    def _validate_response(self, parsed, raw):
        if not raw or len(raw.strip()) == 0:
            return False
        if isinstance(parsed, dict) and 'error' in parsed:
            return False
        return True

    def _invoke(self, prompt, retries=3):
        last_error = None
        for i in range(retries):
            try:
                logger.info(f'LLM request attempt {i + 1}/{retries} to {self.url}')

                r = requests.post(
                    self.url,
                    json={
                        'model': self.model,
                        'prompt': prompt,
                        'stream': False,
                        'options': {'num_predict': 512, 'temperature': 0.7, 'top_p': 0.9}
                    },
                    timeout=self.timeout
                )

                if r.status_code != 200:
                    raise Exception(f'HTTP {r.status_code}: {r.text[:200]}')

                data = r.json()
                if 'response' not in data:
                    raise Exception(f'Invalid response format: {data}')

                response_text = data['response']
                if len(response_text.strip()) == 0:
                    time.sleep(i + 1)
                    continue

                return response_text

            except Exception as e:
                logger.error(f'Error on attempt {i + 1}: {e}')
                last_error = e
                time.sleep(i + 1)

        raise Exception(f'LLM failed after {retries} retries: {last_error}')

    def _parse(self, text):
        if not text: return {}
        text = text.strip()
        # Очистка от мусора (think теги, markdown блоки)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'```$', '', text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Попытка найти JSON внутри текста, если модель добавила лишний текст
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return {'raw': text, 'error': 'Failed to parse JSON'}

    def _log_raw_response(self, agent_name, prompt, raw_response):
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filepath = self.log_dir / f'{agent_name}_{timestamp}.txt'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f'=== PROMPT ===\n{prompt}\n\n=== RAW ===\n{raw_response}\n')