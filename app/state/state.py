class AgentState:

    def __init__(self):
        self.step = "start"

        self.current_idea_id = None

        self.history = []

        self.recovered = False

    def advance(self, next_step):
        self.history.append({
            "from": self.step,
            "to": next_step
        })

        self.step = next_step

    def set_idea(self, idea_id):
        self.current_idea_id = idea_id

    def mark_recovered(self):
        self.recovered = True
