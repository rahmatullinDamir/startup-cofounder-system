import time
import sys
from app.core.orchestrator import Orchestrator
from app.memory.neo4j_client import Neo4jClient

def wait_for_neo4j(max_retries=60, delay=2):
    """Ждём готовности Neo4j перед запуском агентов."""
    client = Neo4jClient()
    for i in range(max_retries):
        try:
            if client.check_connection():
                print("✅ Neo4j connected!")
                return True
        except Exception as e:
            print(f"⏳ Waiting for Neo4j... ({i+1}/{max_retries})")
            time.sleep(delay)
    print("❌ Neo4j not available after retries. Exiting.")
    sys.exit(1)

if __name__ == "__main__":
    wait_for_neo4j()
    orchestrator = Orchestrator()

    user_input = "AI startup for students"

    result = orchestrator.run(user_input)

    print(result)
