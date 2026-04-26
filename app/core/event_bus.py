class EventBus:

    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_name, handler):

        if event_name not in self.listeners:
            self.listeners[event_name] = []

        self.listeners[event_name].append(handler)

    def emit(self, event_name, payload):

        if event_name not in self.listeners:
            return payload

        for handler in self.listeners[event_name]:
            payload = handler(payload)

        return payload
