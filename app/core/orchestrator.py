import os
import logging
from app.core.event_bus import EventBus
from app.core.failure_detector import FailureDetector
from app.agents.ideation import run_ideation
from app.agents.critic import run_critic
from app.agents.planner import run_planner
from app.memory.memory_service import MemoryService
from app.observability.langfuse_client import LangfuseClient

logger = logging.getLogger(__name__)


class Orchestrator:

    def __init__(self):
        self.bus = EventBus()
        self.memory = MemoryService()
        self.failure_detector = FailureDetector(threshold=3)
        self.langfuse = LangfuseClient()

        self._register()

    def _register(self):
        self.bus.subscribe("START", self.ideation_node)
        self.bus.subscribe("IDEA_READY", self.critic_node)
        self.bus.subscribe("CRITIC_DONE", self.planner_node)

    # ---------------- IDEATION ----------------

    def ideation_node(self, input_data):
        trace = self.langfuse.client.trace(name="orchestrator.ideation", input=input_data)

        try:
            idea = run_ideation(input_data)

            idea_id = self.memory.store_idea(idea)

            trace.update(
                output={"idea_id": idea_id},
                metadata={"status": "ok"}
            )

            return self.bus.emit("IDEA_READY", {
                "idea": idea,
                "idea_id": idea_id
            })
        except Exception as e:
            logger.error(f"Ideation failed: {e}")
            trace.update(metadata={"status": "error", "error": str(e)})
            raise

    # ---------------- CRITIC + SELF HEALING ----------------

    def critic_node(self, payload):
        trace = self.langfuse.client.trace(
            name="orchestrator.critic",
            input=payload,
            metadata={"fail_count": self.failure_detector.fail_count}
        )

        try:
            result = run_critic(payload["idea"])

            self.memory.store_evaluation(payload["idea_id"], result)

            if result.get("final_score", 0) < 5:
                self.failure_detector.register_failure()

                if self.failure_detector.should_heal():
                    logger.info("Self-healing triggered: threshold reached")
                    trace.update(metadata={"action": "self_heal", "trigger": "threshold_reached"})

                    last_state = self.memory.rollback()

                    if last_state:
                        self.failure_detector.reset()
                        return self.bus.emit("START", last_state["idea"])
                    else:
                        logger.warning("No checkpoint found for rollback, starting fresh")
                        self.failure_detector.reset()
                        return self.bus.emit("START", payload["idea"])

                trace.update(metadata={"action": "regenerate"})

                new_idea = run_ideation(payload["idea"])

                new_id = self.memory.store_idea(new_idea)

                return self.bus.emit("IDEA_READY", {
                    "idea": new_idea,
                    "idea_id": new_id
                })

            self.failure_detector.reset()
            trace.update(metadata={"action": "approved", "score": result.get("final_score")})

            return self.bus.emit("CRITIC_DONE", {
                "idea": payload["idea"],
                "idea_id": payload["idea_id"],
                "critique": result
            })
        except Exception as e:
            logger.error(f"Critic failed: {e}")
            trace.update(metadata={"status": "error", "error": str(e)})
            raise

    # ---------------- PLANNER ----------------

    def planner_node(self, payload):
        trace = self.langfuse.client.trace(name="orchestrator.planner", input=payload)

        try:
            plan = run_planner(payload["idea"])

            self.memory.store_plan(payload["idea_id"], plan)

            trace.update(
                output={"plan_length": len(str(plan))},
                metadata={"status": "ok"}
            )

            return {
                "idea": payload["idea"],
                "critique": payload["critique"],
                "plan": plan
            }
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            trace.update(metadata={"status": "error", "error": str(e)})
            raise

    def run(self, user_input):
        trace = self.langfuse.client.trace(name="orchestrator.run", input=user_input)

        try:
            result = self.bus.emit("START", user_input)
            trace.update(output=result)
            return result
        except Exception as e:
            logger.error(f"Orchestrator run failed: {e}")
            trace.update(metadata={"status": "error", "error": str(e)})
            raise
        finally:
            self.memory.close()