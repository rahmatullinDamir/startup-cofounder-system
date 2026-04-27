import time
import sys
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from app.core.orchestrator import Orchestrator


def print_formatted_result(result):
    """Форматированный вывод результата (без цветов и эмодзи)."""
    # IDEA
    if "idea" in result:
        idea = result["idea"]
        print("\n--- IDEA ---")
        if isinstance(idea, dict):
            if "problem" in idea:
                print(f"Problem: {idea['problem']}")
            if "solution" in idea:
                print(f"Solution: {idea['solution']}")
            if "target_audience" in idea:
                target = idea['target_audience']
                if isinstance(target, list):
                    print("Target Audience:")
                    for t in target:
                        print(f"  - {t}")
                else:
                    print(f"Target Audience: {target}")
        else:
            print(idea)

    # CRITIQUE
    if "critique" in result:
        critique = result["critique"]
        print("\n--- CRITIQUE ---")
        if isinstance(critique, dict):
            if "final_score" in critique:
                print(f"Score: {critique['final_score']}/10")
            if "verdict" in critique:
                print(f"Verdict: {critique['verdict']}")
            if "problems" in critique:
                problems = critique['problems']
                if isinstance(problems, list) and problems:
                    print("Areas for Improvement:")
                    for i, p in enumerate(problems[:3], 1):
                        p_clean = re.sub(r'\*\*|\*|`', '', str(p))
                        print(f"  {i}. {p_clean[:100]}{'...' if len(p) > 100 else ''}")
        else:
            print(critique)

    # PLAN
    if "plan" in result:
        plan = result["plan"]
        print("\n--- ROADMAP ---")

        phases = []
        if isinstance(plan, dict):
            if "roadmap" in plan and isinstance(plan["roadmap"], list):
                phases = plan["roadmap"]
            elif "phase" in plan:
                phases = [plan]

        if phases:
            for i, phase in enumerate(phases, 1):
                if isinstance(phase, dict):
                    phase_name = phase.get("phase", f"Phase {i}")
                    duration = phase.get("duration", "")
                    tasks = phase.get("tasks", [])

                    print(f"\n{phase_name} ({duration})")
                    if isinstance(tasks, list):
                        for task in tasks:
                            print(f"  - {task}")
                    elif isinstance(tasks, str):
                        print(f"  - {tasks}")
        else:
            print(plan)


def interactive_mode():
    """Интерактивный режим для ввода запросов пользователя."""
    print("\n" + "=" * 60)
    print("Multi-Agent System - Interactive Mode")
    print("=" * 60)
    print("Enter a request to process (or 'quit' to exit)")
    print("-" * 60)

    orchestrator = None

    try:
        while True:
            user_input = input("\nYour request: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            if not user_input:
                print("Please enter a non-empty request")
                continue

            if orchestrator is None:
                orchestrator = Orchestrator()

            print("\n" + "=" * 60)
            print(f"Processing: {user_input}")
            print("=" * 60)

            result = orchestrator.run(user_input)

            print("\n" + "=" * 60)
            print("FINAL RESULT:")
            print("=" * 60)

            if isinstance(result, dict):
                if "error" in result:
                    print(f"\nError: {result['error']}")
                else:
                    print_formatted_result(result)
            else:
                print(result)

            print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    finally:
        if orchestrator:
            orchestrator.memory.close()


if __name__ == "__main__":
    print("Starting Multi-Agent System...")
    interactive_mode()
