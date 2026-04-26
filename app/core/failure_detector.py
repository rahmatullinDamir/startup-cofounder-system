import threading


class FailureDetector:

    def __init__(self, threshold=3):
        self.fail_count = 0
        self.threshold = threshold
        self._lock = threading.Lock()

    def register_failure(self):
        with self._lock:
            self.fail_count += 1

    def reset(self):
        with self._lock:
            self.fail_count = 0

    def should_heal(self):
        with self._lock:
            return self.fail_count >= self.threshold
    
    def get_fail_count(self) -> int:
        """Получить текущее количество неудач (thread-safe)."""
        with self._lock:
            return self.fail_count
    
    def try_heal(self) -> bool:
        """
        Атомарно проверяет и сбрасывает счётчик неудач.
        Возвращает True если healing выполнен.
        """
        with self._lock:
            if self.fail_count >= self.threshold:
                self.fail_count = 0
                return True
            return False
