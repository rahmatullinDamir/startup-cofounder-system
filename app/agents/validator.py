import logging
import json
import re
import threading
from typing import Dict, Any
from app.llm.llm_client import LLMClient
from app.utils.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """Агент-валидатор: проверяет релевантность запроса через LLM."""
    
    def __init__(self, min_confidence: float = 0.6):
        self.llm = LLMClient()
        self.min_confidence = min_confidence
    
    def validate(self, prompt: str) -> Dict[str, Any]:
        """Проверяет запрос через LLM с использованием SOUL и skill."""
        if not prompt or not isinstance(prompt, str):
            return {"is_valid": False, "reason": "Запрос пуст или некорректен", "category": "ERROR", "confidence": 0.0}
        
        prompt = prompt.strip()
        
        if len(prompt) < 5:
            return {"is_valid": False, "reason": "Запрос слишком короткий", "category": "NON_STARTUP", "confidence": 0.9}
        
        if len(prompt) > 100:
            return {"is_valid": False, "reason": "Запрос слишком длинный", "category": "NON_STARTUP", "confidence": 0.9}
        
        try:
            full_prompt = build_prompt('validator', 'validator/validate_request.md', prompt)
            
            result = self.llm.generate(full_prompt, agent_name='validator', metadata={'type': 'validation', 'skill': 'validate_request'})
            
            if isinstance(result, dict) and 'error' in result:
                logger.warning(f"LLM validation error: {result['error']}")
                return {"is_valid": False, "reason": "Ошибка валидации. Попробуйте переформулировать запрос.", "category": "ERROR", "confidence": 0.0}
            
            parsed = result
            if isinstance(result, str):
                # Улучшенный парсинг JSON с поддержкой вложенных объектов
                parsed = self._safe_json_parse(result)
            
            if isinstance(parsed, dict):
                category = parsed.get('category', '').upper()
                confidence = float(parsed.get('confidence', 0))
                reason = parsed.get('reason', 'Неизвестно')
                
                if category == 'STARTUP' and confidence >= self.min_confidence:
                    logger.info(f"Request validated as STARTUP (confidence: {confidence:.2f})")
                    return {"is_valid": True, "reason": reason, "category": "STARTUP", "confidence": confidence}
                
                logger.info(f"Request validated as {category} (confidence: {confidence:.2f})")
                return {"is_valid": False, "reason": "Это не в моей компетенции. Я специализируюсь на генерации и оценке startup-идей.", "category": category, "confidence": confidence}
            
            logger.warning(f"Unexpected validation result: {parsed}")
            return {"is_valid": False, "reason": "Ошибка обработки запроса", "category": "ERROR", "confidence": 0.0}
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"is_valid": False, "reason": "Временная ошибка. Попробуйте позже.", "category": "ERROR", "confidence": 0.0}
    
    def _safe_json_parse(self, text: str) -> Dict[str, Any]:
        """Безопасный парсинг JSON с поддержкой вложенных объектов."""
        if not text:
            return {}
        
        text = text.strip()
        
        # Пытаемся прямой парсинг
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Ищем первый { и последний }
        start = text.find('{')
        end = text.rfind('}')
        
        if start == -1 or end == -1 or end <= start:
            return {'raw': text, 'error': 'No JSON object found'}
        
        json_str = text[start:end+1]
        
        # Пытаемся парсить с рекурсивным поиском
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Упрощаем: убираем лишние переносы строк внутри JSON
        try:
            fixed = re.sub(r'[\r\n]+', ' ', json_str)
            fixed = re.sub(r'\s+', ' ', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        return {'raw': text, 'error': 'Failed to parse JSON'}
    
    def get_stub_response(self) -> Dict[str, Any]:
        """Возвращает заглушку для нерелевантных запросов."""
        return {"idea": None, "critique": None, "plan": None, "error": "Это не в моей компетенции. Я специализируюсь на генерации и оценке startup-идей. Попробуйте: 'startup idea для...', 'бизнес-идея в сфере...', 'как начать бизнес в...'."}


_validator = None
_validator_lock = threading.Lock()

def get_validator() -> ValidatorAgent:
    global _validator
    if _validator is None:
        with _validator_lock:
            if _validator is None:
                _validator = ValidatorAgent()
    return _validator

def run_validator(prompt: str) -> Dict[str, Any]:
    validator = get_validator()
    return validator.validate(prompt)
