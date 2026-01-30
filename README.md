# SDLC Agent

Автоматизированная агентная система для полного цикла разработки ПО (SDLC) внутри GitHub.

Система имитирует работу разработчика и ревьюера: анализирует задачи из Issues, вносит изменения в код, создаёт Pull Request, запускает CI/CD, анализирует результаты и принимает решение о завершении или повторе цикла.

## Основной сценарий работы

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    Issue     │      │  Code Agent  │      │    PR + CI   │
│   создан     │─────►│  генерирует  │─────►│   создан     │
│              │      │     код      │      │              │
└──────────────┘      └──────────────┘      └──────┬───────┘
                                                   │
                                                   ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    Merge     │      │   APPROVE    │      │   Reviewer   │
│    ready     │◄─────│      или     │◄─────│    Agent     │
│              │      │   COMMENT    │      │  анализирует │
└──────────────┘      └──────────────┘      └──────────────┘
                             │
                             │ REQUEST_CHANGES
                             ▼
                      ┌──────────────┐
                      │  Code Agent  │
                      │  исправляет  │────────┐
                      └──────────────┘        │
                             ▲                │
                             └────────────────┘
                              (повтор цикла)
```

1. Пользователь создаёт Issue с описанием задачи (label: `auto-fix`)
2. **Code Agent** анализирует требования, генерирует код, создаёт PR
3. Автоматически запускается CI/CD pipeline (linting, tests)
4. **Reviewer Agent** анализирует изменения, проверяет CI, сравнивает с Issue
5. Результат публикуется в PR как code review
6. При `REQUEST_CHANGES` — Code Agent исправляет, цикл повторяется
7. При `APPROVE` — PR готов к merge

## Архитектура

### Code Agent

- Получает и парсит текст Issue
- Анализирует требования задачи
- Генерирует и модифицирует код
- Автоматически форматирует через `ruff format`
- Создаёт Pull Request
- Исправляет код по замечаниям Reviewer Agent

### Reviewer Agent

- Анализирует diff в Pull Request
- Проверяет результаты CI jobs
- Сравнивает реализацию с требованиями Issue
- Проверяет код на уязвимости (OWASP)
- Публикует результаты в PR (APPROVE / REQUEST_CHANGES / COMMENT)

## Технические требования

- **Python**: 3.11+
- **LLM**: OpenRouter (Gemini, Claude), OpenAI, Groq, Mistral
- **GitHub**: PyGithub для API
- **Качество кода**: ruff, pytest
- **CI/CD**: GitHub Actions
- **Контейнеризация**: Docker, docker-compose

## Быстрый старт

### Запуск через Docker (рекомендуется)

```bash
# 1. Клонировать репозиторий
# SSH
git clone git@github.com:ekukovenko/ivan-code.git
# или HTTPS
git clone https://github.com/ekukovenko/ivan-code.git
cd ivan-code

# 2. Настроить переменные окружения
cp .env.example .env
# Отредактировать .env: LLM_API_KEY, GITHUB_TOKEN, GITHUB_REPO, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, также можно настроить время ожидания завершения CI - CI_WAIT_TIMEOUT и максимальное кол-во итераций агентов - MAX_ITERATIONS

# 3. Запустить контейнер
docker-compose up -d

# 4. Создать issue вручную на гитхабе (обязательно указать путь к файлу, название функции или класса и что делает)
# Пример хорошего Issue:
#   Title: Add multiply(a,b) to app/math.py
#   Body: Возвращает произведение

#   Примеры плохого Issue:
#   Title: титл
#   Body: напиши функцию
#   LLM не знает куда и что писать ):

# 5. Запустить обработку issue
docker-compose run --rm ivan-code-sdlc-agent python -m src.cli issue <номер_issue>
```

### Запуск локально

```bash
# 1. Установить зависимости
pip install -e .

# 2. Настроить .env
cp .env.example .env

# 3. Создать issue вручную на гитхабе (также как было описано выше)

# 4. Запустить обработку Issue
python -m src.cli issue <номер>
```

### Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| `LLM_API_KEY` | API ключ LLM провайдера | Да |
| `GITHUB_TOKEN` | GitHub Personal Access Token | Да |
| `GITHUB_REPO` | Целевой репозиторий (owner/repo) | Да |
| `LLM_PROVIDER` | Провайдер (openrouter, openai, groq) | Нет (default: openrouter) |
| `LLM_MODEL` | Модель LLM | Нет (default: gemini-2.5-flash) |
| `MAX_ITERATIONS` | Макс. итераций цикла | Нет (default: 5) |

## CLI команды

```bash
# Полный SDLC цикл (Code Agent → CI → Reviewer → Fix → ...)
python -m src.cli issue <issue_number>

# Только Code Agent (создать PR без review)
python -m src.cli code <issue_number>

# Только Reviewer Agent (проверить существующий PR)
python -m src.cli review <pr_number> --issue <issue_number>

# Webhook сервер (реализован, требует публичного URL для работы с GitHub)
python -m src.cli server --port 8080
```

## GitHub Actions

Workflows реализованы, но не протестированы. Агенты запускались вручную через CLI/Docker. 

Workflow автоматически запускается при:
- Создании Issue с label `auto-fix` или `ai-agent`
- Создании/обновлении PR с веткой `issue-*-auto`

Настройка в целевом репозитории:
1. Secrets → `LLM_API_KEY`
2. Variables → `LLM_PROVIDER`, `LLM_MODEL` (опционально)

## Примеры работы

### Тестовый репозиторий

[ekukovenko/test-todo-app](https://github.com/ekukovenko/test-todo-app)

### Примеры Issues и PRs

| Issue | PR | Описание | Итерации | Результат |
|-------|-----|----------|----------|-----------|
| [#40](https://github.com/ekukovenko/test-todo-app/issues/40) | [#41](https://github.com/ekukovenko/test-todo-app/pull/41) | Add multiply function | 1 | APPROVE |
| [#31](https://github.com/ekukovenko/test-todo-app/issues/31) | [#32](https://github.com/ekukovenko/test-todo-app/pull/32) | Session memory + test | 1 | APPROVE |
| [#29](https://github.com/ekukovenko/test-todo-app/issues/29) | [#30](https://github.com/ekukovenko/test-todo-app/pull/30) | Add square(x) function | 1 | APPROVE |

### Пример Issue

```markdown
Title: Add multiply function

Body:
Добавить функцию multiply(a, b) в файл app/math_utils.py,
которая возвращает произведение двух чисел.
```

### Пример Review от Reviewer Agent

```markdown
👀 **Reviewer Agent** ✅ APPROVE

PR добавляет функцию multiply в app/math_utils.py, как описано в задаче.
CI проходит, уязвимости не обнаружены.

---
*Статус: APPROVE (отправлено как COMMENT из-за ограничений GitHub)*
```

## Структура проекта

```
├── src/
│   ├── agents/           # Code Agent и Reviewer Agent
│   │   ├── code_agent.py
│   │   └── reviewer_agent.py
│   ├── core/             # Конфигурация и оркестратор
│   │   ├── config.py
│   │   └── orchestrator.py
│   ├── github/           # GitHub API клиент
│   ├── tools/            # Инструменты агентов
│   │   ├── code_tools.py    # write_file, check_style, security
│   │   └── review_tools.py  # get_diff, submit_review
│   ├── webhook/          # Webhook сервер
│   └── cli.py            # CLI интерфейс
├── tests/                # Тесты
├── .github/workflows/    # GitHub Actions
│   ├── ci.yml            # Lint + Tests
│   └── sdlc-agent.yml    # SDLC automation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

## Особенности реализации

- **Изоляция агентов**: Code Agent и Reviewer Agent работают независимо
- **Session memory**: Агенты помнят контекст в рамках одного Issue
- **Автоформатирование**: `ruff format` применяется автоматически при записи файлов
- **Security checks**: Проверка на OWASP уязвимости (SQL injection, XSS, secrets)
- **CI wait**: Оркестратор ждёт завершения CI перед review
- **Fallback reviews**: Если GitHub не позволяет APPROVE/REQUEST_CHANGES на свой PR, постится как COMMENT с маркером
- **LangFuse tracing**: Опциональная трассировка для отладки (переменные `LANGFUSE_*`)

## Тестирование

```bash
# Установить dev зависимости
pip install -e ".[dev]"

# Unit тесты
pytest -v

# Интеграционные тесты с LLM (требует LLM_API_KEY)
RUN_INTEGRATION_TESTS=1 pytest -v
```