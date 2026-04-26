#!/usr/bin/env python3
"""
Проверка всех зависимостей перед запуском проекта.
"""

import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def print_section(title: str):
    """Вывод заголовка секции."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)


def check_python_version():
    """Проверяет версию Python."""
    print_section("Python версия")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 3.9:
        print("✓ Версия Python подходит (>= 3.9)")
        return True
    else:
        print("✗ Требуется Python >= 3.9")
        return False


def check_packages():
    """Проверяет установленные пакеты."""
    print_section("Python пакеты")
    
    required_packages = [
        'fastapi', 'uvicorn', 'pydantic', 'requests', 'neo4j',
        'python-dotenv', 'langfuse'
    ]
    
    missing = []
    installed = []
    
    for package in required_packages:
        try:
            __import__(package)
            installed.append(package)
        except ImportError:
            missing.append(package)
    
    if installed:
        print(f"✓ Установлено: {', '.join(installed)}")
    
    if missing:
        print(f"✗ Отсутствуют: {', '.join(missing)}")
        print(f"\nУстановите пропущенные пакеты:")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    return True


def check_ollama() -> bool:
    """Проверяет Ollama и модель."""
    print_section("Ollama")
    
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print("✗ Ollama не установлен или не найден в PATH")
            print("Установите с: https://ollama.ai")
            return False
        
        print(f"✓ Ollama: {result.stdout.strip()}")
        
        # Проверка модели
        model_name = os.getenv('LLM_MODEL', 'qwen3.5:2b')
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if model_name in result.stdout:
            print(f"✓ Модель {model_name} установлена")
            return True
        else:
            print(f"⚠ Модель {model_name} не найдена")
            print(f"  Загрузите: ollama pull {model_name}")
            print(f"  Или используйте скрипт: python scripts/setup_ollama.py --auto")
            return False
            
    except FileNotFoundError:
        print("✗ Ollama не найден в PATH")
        return False
    except Exception as e:
        print(f"✗ Ошибка проверки Ollama: {e}")
        return False


def check_neo4j() -> bool:
    """Проверяет подключение к Neo4j."""
    print_section("Neo4j")
    
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')
    
    print(f"URI: {uri}")
    print(f"User: {user}")
    
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            result = session.run("RETURN 1 AS test")
            record = result.single()
            
            if record and record[0] == 1:
                print("✓ Подключение к Neo4j успешно")
                driver.close()
                return True
            else:
                print("✗ Не удалось выполнить запрос к Neo4j")
                driver.close()
                return False
                
    except Exception as e:
        print(f"✗ Ошибка подключения к Neo4j: {e}")
        print("Убедитесь, что Neo4j запущен:")
        print("  docker-compose up -d")
        return False


def check_langfuse() -> bool:
    """Проверяет конфигурацию Langfuse (опционально)."""
    print_section("Langfuse (опционально)")
    
    public_key = os.getenv('LANGFUSE_PUBLIC_KEY', '')
    secret_key = os.getenv('LANGFUSE_SECRET_KEY', '')
    host = os.getenv('LANGFUSE_HOST', 'http://localhost:3000')
    
    if not public_key or not secret_key:
        print("⚠ Langfuse не настроен (оставьте пустым, если не используете)")
        print("  Это не критично - приложение будет работать без observability")
        return True
    
    print(f"Host: {host}")
    print("✓ Langfuse настроен")
    return True


def check_imports() -> bool:
    """Проверяет импорт модулей проекта."""
    print_section("Модули проекта")
    
    modules = [
        'app.core.orchestrator',
        'app.agents.validator',
        'app.agents.ideation',
        'app.agents.critic',
        'app.agents.planner',
        'app.memory.memory_service',
        'app.llm.llm_client',
    ]
    
    failed = []
    
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except Exception as e:
            print(f"✗ {module}: {e}")
            failed.append(module)
    
    if failed:
        print(f"\n✗ Ошибки импорта: {', '.join(failed)}")
        return False
    
    return True


def main():
    """Основная функция."""
    print("\n" + "=" * 60)
    print(" ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    print("=" * 60)
    
    results = []
    
    results.append(("Python", check_python_version()))
    results.append(("Пакеты", check_packages()))
    results.append(("Ollama", check_ollama()))
    results.append(("Neo4j", check_neo4j()))
    results.append(("Langfuse", check_langfuse()))
    results.append(("Импорт модулей", check_imports()))
    
    # Итоговый отчёт
    print_section("ИТОГ")
    
    all_passed = True
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ Все проверки пройдены! Проект готов к запуску.")
        print("\nЗапуск:")
        print("  python main.py")
        print("  # или")
        print("  uvicorn app.api.server:app --reload")
        return 0
    else:
        print("⚠ Некоторые проверки не пройдены. Исправьте ошибки выше.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
