class FailureDetector:

    def __init__(self, threshold=3):
        self.fail_count = 0
        self.threshold = threshold

    def register_failure(self):
        self.fail_count += 1

    def reset(self):
        self.fail_count = 0

    def should_heal(self):
        return self.fail_count >= self.threshold