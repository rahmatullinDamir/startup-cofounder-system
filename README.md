# Multi-Agent Startup Cofounder System

Мультиагентная система для генерации и оценки startup-идей.

## Агенты

- **Ideation** — генерирует startup-гипотезы
- **Critic** — оценивает качество идей
- **Planner** — строит roadmap для одобренных идей

## Архитектура

- **Orchestrator** — координирует работу агентов
- **Event Bus** — pub/sub механизм для связи
- **Failure Detector** — self-healing при неудачах
- **Memory** — Neo4j + Graphiti RAG

## Технологии

| Компонент | Технология |
|-----------|------------|
| LLM Engine | Ollama (llama3.2, qwen, gemma) |
| Graph DB | Neo4j |
| RAG | Graphiti (графовый поиск) |
| Observability | Langfuse |
| Фреймворк | Свой (Event Bus + Orchestrator) |

## Установка

1. Клонируйте репозиторий
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Запустите инфраструктуру:
   ```bash
   cd docker
   docker-compose up -d
   ```
4. Запустите Ollama с моделью:
   ```bash
   ollama pull llama3.2
   ollama serve
   ```
5. Индексируйте SOUL.md файлы:
   ```bash
   python -m app.memory.index_souls
   ```
6. Запустите систему:
   ```bash
   python main.py
   ```

## Документация

- [Архитектура](docs/architecture.md) — описание архитектуры и компонентов
- [Графовый RAG](docs/rag_usage.md) — использование Graphiti RAG
- [Память](docs/memory_architecture.md) — обоснование выбора системы памяти

## Как работает

1. Пользователь вводит запрос
2. **Ideation** генерирует идею (используя RAG-контекст)
3. **Critic** оценивает идею
4. Если оценка < 5 → self-healing (rollback + повтор)
5. Если оценка >= 5 → **Planner** строит roadmap
6. Результат возвращается пользователю

## Наблюдаемость

Все вызовы LLM логируются в **Langfuse**:
- Метрики: latency, success rate
- Metadata: agent, skill, rag_used
- Трейсы: полный флоу от запроса до результата

Доступно по адресу: http://localhost:3000

## Лицензия

MIT
