from app.core.event_bus import EventBus
from app.agents.ideation import run_ideation
from app.agents.critic import run_critic
from app.agents.planner import run_planner
from app.memory.memory_service import MemoryService


class Orchestrator:

    def __init__(self):

        self.bus = EventBus()
        self.memory = MemoryService()

        self.fail_counter = 0

        self._register()

    def _register(self):

        self.bus.subscribe("START", self.ideation_node)
        self.bus.subscribe("IDEA_READY", self.critic_node)
        self.bus.subscribe("CRITIC_DONE", self.planner_node)

    # ---------------- IDEATION ----------------

    def ideation_node(self, input_data):

        idea = run_ideation(input_data)

        idea_id = self.memory.store_idea(idea)

        return self.bus.emit("IDEA_READY", {
            "idea": idea,
            "idea_id": idea_id
        })

    # ---------------- CRITIC + SELF HEALING ----------------

    def critic_node(self, payload):

        result = run_critic(payload["idea"])

        self.memory.store_evaluation(payload["idea_id"], result)

        if result["final_score"] < 5:

            self.fail_counter += 1

            # 🔥 SELF-HEALING
            if self.fail_counter >= 3:

                last_state = self.memory.rollback()

                self.fail_counter = 0

                return self.bus.emit("START", last_state["idea"])

            new_idea = run_ideation(payload["idea"])

            new_id = self.memory.store_idea(new_idea)

            return self.bus.emit("IDEA_READY", {
                "idea": new_idea,
                "idea_id": new_id
            })

        self.fail_counter = 0

        return self.bus.emit("CRITIC_DONE", {
            "idea": payload["idea"],
            "idea_id": payload["idea_id"],
            "critique": result
        })

    # ---------------- PLANNER ----------------

    def planner_node(self, payload):

        plan = run_planner(payload["idea"])

        self.memory.store_plan(payload["idea_id"], plan)

        return {
            "idea": payload["idea"],
            "critique": payload["critique"],
            "plan": plan
        }

    def run(self, user_input):

        return self.bus.emit("START", user_input)