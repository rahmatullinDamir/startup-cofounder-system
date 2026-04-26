from app.memory.neo4j_client import Neo4jClient


class MemoryService:

    def __init__(self):
        self.db = Neo4jClient()

    # -------------------------
    # STORE
    # -------------------------

    def store_idea(self, idea):
        result = self.db.query("""
            CREATE (i:Idea {content: $idea})
            RETURN id(i) as id
        """, {"idea": str(idea)})

        return result[0]["id"]

    def store_evaluation(self, idea_id, evaluation):
        self.db.query("""
            MATCH (i:Idea) WHERE id(i) = $id
            CREATE (e:Evaluation {content: $eval, score: $score})
            CREATE (i)-[:HAS_EVAL]->(e)
        """, {
            "id": idea_id,
            "eval": str(evaluation),
            "score": evaluation.get("final_score", 0)
        })

    def store_plan(self, idea_id, plan):
        self.db.query("""
            MATCH (i:Idea) WHERE id(i) = $id
            CREATE (p:Plan {content: $plan})
            CREATE (i)-[:HAS_PLAN]->(p)
        """, {
            "id": idea_id,
            "plan": str(plan)
        })

    def link_iteration(self, old_id, new_id, reason):
        self.db.query("""
            MATCH (a:Idea), (b:Idea)
            WHERE id(a) = $old AND id(b) = $new
            CREATE (a)-[:ITERATED_TO {reason: $reason}]->(b)
        """, {
            "old": old_id,
            "new": new_id,
            "reason": reason
        })

    def store_failure(self, idea_id, reason):
        self.db.query("""
            MATCH (i:Idea) WHERE id(i) = $id
            CREATE (f:Failure {reason: $reason})
            CREATE (i)-[:FAILED]->(f)
        """, {
            "id": idea_id,
            "reason": reason
        })

    # -------------------------
    # READ
    # -------------------------

    def get_similar_failures(self):
        result = self.db.query("""
            MATCH (i:Idea)-[:FAILED]->(f)
            RETURN i.content as idea, f.reason as reason
            LIMIT 5
        """)

        return result

    def get_best_ideas(self):
        result = self.db.query("""
            MATCH (i:Idea)-[:HAS_EVAL]->(e)
            WHERE e.score >= 7
            RETURN i.content as idea, e.score as score
            ORDER BY e.score DESC
            LIMIT 3
        """)

        return result

    def get_last_good_idea(self):
        result = self.db.query("""
            MATCH (i:Idea)-[:HAS_EVAL]->(e)
            WHERE e.score >= 7
            RETURN i.content as idea
            ORDER BY e.score DESC
            LIMIT 1
        """)

        return result[0]["idea"] if result else None

    # -------------------------
    # CHECKPOINT / ROLLBACK
    # -------------------------

    def store_checkpoint(self, idea_id, idea_content):
        self.db.query("""
            MATCH (i:Idea) WHERE id(i) = $id
            CREATE (c:Checkpoint {content: $content, timestamp: timestamp()})
            CREATE (i)-[:HAS_CHECKPOINT]->(c)
        """, {
            "id": idea_id,
            "content": str(idea_content)
        })

    def rollback(self):
        result = self.db.query("""
            MATCH (i:Idea)-[:HAS_CHECKPOINT]->(c)
            RETURN i.content as idea, i.id as id
            ORDER BY c.timestamp DESC
            LIMIT 1
        """)

        if not result:
            return None

        return {
            "idea": result[0]["idea"],
            "idea_id": result[0]["id"]
        }

    def close(self):
        self.db.close()
