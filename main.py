import time
import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from app.core.orchestrator import Orchestrator

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
                    print(json.dumps(result, indent=2, ensure_ascii=False))
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
