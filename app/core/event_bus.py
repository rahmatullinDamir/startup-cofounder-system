import threading
import logging

logger = logging.getLogger(__name__)


class EventBus:

    def __init__(self):
        self.listeners = {}
        self._lock = threading.Lock()

    def subscribe(self, event_name, handler):
        with self._lock:
            if event_name not in self.listeners:
                self.listeners[event_name] = []
            self.listeners[event_name].append(handler)

    def emit(self, event_name, payload):
        with self._lock:
            handlers = list(self.listeners.get(event_name, []))
        
        failed_handlers = []
        for handler in handlers:
            try:
                result = handler(payload)
                if result is not None:
                    payload = result
            except Exception as e:
                logger.error(f"Handler {handler.__name__} failed for event {event_name}: {e}")
                failed_handlers.append({"handler": handler.__name__, "error": str(e)})
        
        if failed_handlers:
            logger.warning(f"Failed handlers for {event_name}: {failed_handlers}")
            # Не прерываем выполнение, продолжаем с другими handlers
        
        return payload
