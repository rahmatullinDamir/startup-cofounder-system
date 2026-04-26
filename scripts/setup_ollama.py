#!/usr/bin/env python3
"""
Скрипт для автоматической проверки и загрузки модели Ollama.
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


def check_ollama_installed() -> bool:
    """Проверяет, установлен ли Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"✓ Ollama установлен: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        print("✗ Ollama не найден. Установите с https://ollama.ai")
    except Exception as e:
        print(f"✗ Ошибка проверки Ollama: {e}")
    return False


def get_installed_models() -> list:
    """Получает список установленных моделей."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            # Парсим вывод (формат: NAME ID SIZE MODIFIED)
            lines = result.stdout.strip().split('\n')[1:]  # Пропускаем заголовок
            models = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            return models
    except Exception as e:
        print(f"⚠ Ошибка получения списка моделей: {e}")
    return []


def check_model_installed(model_name: str) -> bool:
    """Проверяет, установлена ли конкретная модель."""
    models = get_installed_models()
    return model_name in models


def pull_model(model_name: str) -> bool:
    """Загружает модель через Ollama."""
    print(f"\nЗагрузка модели {model_name}...")
    print("Это может занять несколько минут в зависимости от скорости сети.\n")
    
    try:
        # Запускаем процесс с выводом в реальном времени
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Читаем вывод по строкам
        for line in process.stdout:
            print(line.strip(), flush=True)
        
        process.wait()
        
        if process.returncode == 0:
            print(f"\n✓ Модель {model_name} успешно загружена!")
            return True
        else:
            print(f"\n✗ Ошибка загрузки модели (код: {process.returncode})")
            return False
            
    except KeyboardInterrupt:
        print("\n\n⚠ Загрузка прервана пользователем")
        return False
    except Exception as e:
        print(f"\n✗ Ошибка загрузки модели: {e}")
        return False


def setup_model(model_name: str = None) -> bool:
    """
    Проверяет и загружает модель если нужно.
    
    Args:
        model_name: Имя модели (по умолчанию из .env)
    
    Returns:
        True если модель готова к использованию
    """
    if model_name is None:
        model_name = os.getenv('LLM_MODEL', 'qwen3.5:2b')
    
    print("=" * 60)
    print("Проверка модели Ollama")
    print("=" * 60)
    
    # 1. Проверка установки Ollama
    if not check_ollama_installed():
        return False
    
    # 2. Проверка наличия модели
    if check_model_installed(model_name):
        print(f"✓ Модель {model_name} уже установлена")
        return True
    
    print(f"⚠ Модель {model_name} не найдена")
    
    # 3. Запрос на загрузку
    response = input(f"\nЗагрузить модель {model_name}? (y/n): ").strip().lower()
    
    if response in ['y', 'yes', 'да', 'д']:
        return pull_model(model_name)
    else:
        print("Модель не загружена. Приложение может не работать корректно.")
        return False


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Проверка и загрузка моделей Ollama")
    parser.add_argument("--model", "-m", help="Имя модели для загрузки")
    parser.add_argument("--auto", "-a", action="store_true", help="Автоматическая загрузка без запроса")
    parser.add_argument("--list", "-l", action="store_true", help="Показать список установленных моделей")
    
    args = parser.parse_args()
    
    if args.list:
        models = get_installed_models()
        if models:
            print("\nУстановленные модели:")
            for model in models:
                print(f"  - {model}")
        else:
            print("\nНет установленных моделей")
        return
    
    model_name = args.model or os.getenv('LLM_MODEL', 'qwen3.5:2b')
    
    if args.auto:
        success = setup_model(model_name)
        sys.exit(0 if success else 1)
    else:
        # Интерактивный режим
        success = setup_model(model_name)
        if not success:
            print("\nВы можете загрузить модель вручную:")
            print(f"  ollama pull {model_name}")
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
