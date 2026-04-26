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
        self.model = os.getenv('LLM_MODEL', 'llama3.2:3b')
        self.url = os.getenv('LLM_URL', 'http://host.docker.internal:11434/api/generate')
        self.timeout = int(os.getenv('LLM_TIMEOUT', '180'))
        self._ensure_log_dir()

    @property
    def langfuse(self):
        """Lazy initialization - returns global singleton."""
        return get_langfuse_client()

    def _ensure_log_dir(self):
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

            # Используем create_span вместо start_observation
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
            logger.error('Empty response from LLM')
            return False
        if isinstance(parsed, dict) and 'error' in parsed:
            logger.error(f'Response contains error: {parsed.get("error")}')
            return False
        return True

    def _invoke(self, prompt, retries=3):
        last_error = None

        for i in range(retries):
            try:
                logger.info(f'LLM request attempt {i+1}/{retries} to {self.url} with model {self.model}')
                
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

                logger.info(f'Response status: {r.status_code}')

                if r.status_code != 200:
                    raise Exception(f'HTTP {r.status_code}: {r.text[:200]}')

                data = r.json()

                if 'response' not in data:
                    raise Exception(f'Invalid response format: {data}')

                response_text = data['response']
                logger.info(f'Raw response length: {len(response_text)} chars')
                
                if len(response_text.strip()) == 0:
                    logger.warning('Empty response, retrying...')
                    last_error = ValueError('Empty response')
                    time.sleep(i + 1)
                    continue

                return response_text

            except requests.exceptions.Timeout:
                logger.error(f'Timeout on attempt {i+1}')
                last_error = TimeoutError(f'Request timed out (>{self.timeout}s)')
                time.sleep(i + 1)
            except Exception as e:
                logger.error(f'Error on attempt {i+1}: {e}')
                last_error = e
                time.sleep(i + 1)

        raise Exception(f'LLM failed after {retries} retries: {last_error}')

    def _parse(self, text):
        if not text or len(text.strip()) == 0:
            return {}
        
        text = text.strip()
        text = re.sub(r'^/\s*no_think\s*\n?', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'^\s*\s*', '', text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r'^\s*</think>\s*', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'^```json\s*', '', text).strip()
        text = re.sub(r'```$', '', text, flags=re.IGNORECASE).strip()

        try:
            result = json.loads(text)
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except json.JSONDecodeError:
            pass

        match = re.search(r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}', text, re.DOTALL)
        if match:
            json_str = match.group()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            try:
                def fix_newlines_in_strings(m):
                    s = m.group(0)
                    return s.replace('\n', '\\n').replace('\r', '\\r')
                
                fixed = re.sub(r'"(?:[^"\\]|\\.)*\n(?:[^"\\]|\\.)*"', fix_newlines_in_strings, json_str)
                return json.loads(fixed)
            except json.JSONDecodeError as e:
                logger.debug(f'First fix failed: {e}')
                pass

            try:
                fixed = re.sub(r',\s*\n\s*', ', ', json_str)
                fixed = re.sub(r':\s*\n\s*', ': ', fixed)
                fixed = re.sub(r'\[\s*\n\s*', '[', fixed)
                fixed = re.sub(r'\s*\n\s*\]', ']', fixed)
                fixed = re.sub(r'\{\s*\n\s*', '{', fixed)
                fixed = re.sub(r'\s*\n\s*\}', '}', fixed)
                return json.loads(fixed)
            except json.JSONDecodeError as e:
                logger.debug(f'Second fix failed: {e}')
                pass

        return {'raw': text, 'error': 'Failed to parse JSON after multiple attempts'}

    def _log_raw_response(self, agent_name, prompt, raw_response):
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filename = f'{agent_name}_{timestamp}.txt'
        filepath = self.log_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f'=== PROMPT ===\n{prompt}\n\n=== RAW RESPONSE ===\n{raw_response}\n')
        
        logger.info(f'Raw response saved to: {filepath}')
