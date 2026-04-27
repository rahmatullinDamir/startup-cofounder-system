import os
from neo4j import GraphDatabase
from app.observability.langfuse_client import LangfuseClient


class Neo4jClient:

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.langfuse = LangfuseClient()
        
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def check_connection(self):
        """Проверка подключения к Neo4j."""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    def query(self, cypher, params=None):
        trace = self.langfuse.create_trace(name="neo4j_query")
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, params or {})
                data = [record.data() for record in result]
                
            trace.update(
                input={"cypher": cypher, "params": params},
                output={"rows": len(data)},
                metadata={"status": "ok"}
            )
            return data
        except Exception as e:
            trace.update(
                metadata={"status": "error", "error": str(e)}
            )
            raise

    def close(self):
        self.driver.close()
