from app.core.orchestrator import Orchestrator

if __name__ == "__main__":
    orchestrator = Orchestrator()

    user_input = "AI startup for students"

    result = orchestrator.run(user_input)

    print(result)
