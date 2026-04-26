from app.memory.neo4j_client import Neo4jClient


class GraphitiMemory:

    def __init__(self):
        self.db = Neo4jClient()

    def add_idea(self, idea):
        return self.db.create_node("Idea", idea)

    def add_evaluation(self, idea_id, eval):
        e = self.db.create_node("Evaluation", eval)
        self.db.create_rel(idea_id, e, "HAS_EVAL")
        return e

    def add_plan(self, idea_id, plan):
        p = self.db.create_node("Plan", plan)
        self.db.create_rel(idea_id, p, "HAS_PLAN")
        return p

    def add_failure(self, idea_id, reason):
        f = self.db.create_node("Failure", {"reason": reason})
        self.db.create_rel(idea_id, f, "FAILED")
