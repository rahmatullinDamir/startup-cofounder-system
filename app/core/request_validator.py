import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)


class RequestValidator:
    """Валидатор запросов - фильтрует нерелевантные запросы."""
    
    # Ключевые слова, указывающие на startup/бизнес-тематику
    STARTUP_KEYWORDS = [
        'startup', 'стартап', 'бизнес', 'идея', 'проект', 'компании',
        'продукт', 'услуга', 'рынок', 'клиенты', 'покупатели',
        'инвестиции', 'финансирование', 'монетизация', 'revenue',
        'проблема', 'solution', 'решение', 'инновация', 'технология',
        'app', 'приложение', 'платформа', 'сервис', 'система',
        'образование', 'healthcare', 'медицина', 'финтех', 'finance',
        'еда', 'food', 'доставка', 'delivery', 'школа', 'учеба',
        'ecommerce', 'торговля', 'магазин', 'онлайн', 'digital'
    ]
    
    # Паттерны нерелевантных запросов
    IRRELEVANT_PATTERNS = [
        r'\b(привет|здравствуйте|как дела|что нового|погода)\b',
        r'\b(кто ты|что ты|твоё имя|кто создал)\b',
        r'\b(напиши стих|напиши песню|расскажи шутку)\b',
        r'\b(код для|программа для|скрипт)\b',
        r'\b(реферат|курсовая|диплом|домашнее задание)\b',
    ]
    
    MIN_PROMPT_LENGTH = 5
    MAX_PROMPT_LENGTH = 500
    
    def __init__(self, min_score=3):
        self.min_score = min_score
    
    def validate(self, prompt: str) -> Tuple[bool, str]:
        """Проверяет релевантность запроса."""
        if not prompt or not isinstance(prompt, str):
            return False, "Запрос пуст или некорректен"
        
        prompt_lower = prompt.lower().strip()
        
        if len(prompt_lower) < self.MIN_PROMPT_LENGTH:
            return False, f"Запрос слишком короткий (минимум {self.MIN_PROMPT_LENGTH} символов)"
        
        if len(prompt_lower) > self.MAX_PROMPT_LENGTH:
            return False, f"Запрос слишком длинный (максимум {self.MAX_PROMPT_LENGTH} символов)"
        
        for pattern in self.IRRELEVANT_PATTERNS:
            if re.search(pattern, prompt_lower):
                return False, "Это не в моей компетенции. Я специализируюсь на генерации и оценке startup-идей."
        
        score = sum(1 for keyword in self.STARTUP_KEYWORDS if keyword in prompt_lower)
        
        if score < self.min_score:
            return False, "Это не в моей компетенции. Я специализируюсь на генерации и оценке startup-идей. Попробуйте запрос типа: 'startup idea для...' или 'бизнес-идея в сфере...'."
        
        logger.info(f"Request validated: score={score}/{len(self.STARTUP_KEYWORDS)}")
        return True, None
    
    def get_stub_response(self) -> dict:
        """Возвращает заглушку для нерелевантных запросов."""
        return {
            "idea": None,
            "critique": None,
            "plan": None,
            "error": "Это не в моей компетенции. Я специализируюсь на генерации и оценке startup-идей. Попробуйте запрос типа: 'startup idea для...' или 'бизнес-идея в сфере...'."
        }
