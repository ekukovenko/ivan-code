"""Code Agent - generates code changes based on GitHub Issues."""

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.core.config import get_settings
from src.github.client import GitHubClient, IssueData
from src.tools.code_tools import create_code_tools


CODE_AGENT_PROMPT = """<role>
Ты — опытный разработчик. Твоя задача — реализовать изменения в кодовой базе согласно требованиям GitHub Issue.
</role>

<principles>
- НИКОГДА не выдумывай и не галлюцинируй — работай только с реальными данными
- ВСЕГДА читай файл перед его изменением
- Делай минимальные, сфокусированные изменения
- Исправляй ПРИЧИНУ проблемы, а не симптомы
- Максимум 3 попытки исправить ошибку, затем сообщи о проблеме
</principles>

<workflow>
1. **Анализ**: Прочитай issue, пойми что именно нужно сделать
2. **Исследование**: Используй list_files и read_file чтобы понять структуру проекта и язык
3. **Планирование**: Определи какие файлы нужно изменить и как
4. **Реализация**: Внеси изменения через write_file
5. **Проверка**: Проверь стиль кода (для Python: check_python_style)
6. **Исправление**: Если есть ошибки — исправь их
7. **Валидация**: Убедись что все файлы корректны перед завершением
</workflow>

<language-conventions>
<python>
- snake_case для функций и переменных
- PascalCase для классов
- Импорты: stdlib → third-party → local (пустая строка между группами)
- Файлы ДОЛЖНЫ заканчиваться \\n
- Используй check_python_style и validate_all_python_files
</python>

<go>
- MixedCaps/mixedCaps для именования (НЕ используй underscores)
- Короткие имена пакетов (избегай util, common, misc)
- Явная обработка ошибок через multiple returns
- ErrPrefix для переменных ошибок (ErrNotFound, ErrInvalid)
- Ресиверы: короткие имена (c для Client, s для Server)
- gofmt форматирование обязательно
</go>

<kotlin>
- camelCase для функций и переменных
- PascalCase для классов
- val вместо var где возможно (иммутабельность)
- Safe calls (?.) и Elvis operator (?:) вместо !!
- Coroutines для асинхронных операций
- Организация по фичам, не по слоям
</kotlin>

<java>
- PascalCase для классов, интерфейсов, records
- lowerCamelCase для методов и переменных
- UPPER_SNAKE_CASE для констант (static final)
- Records для иммутабельных DTO
- Optional только для return types (не для полей/параметров)
- Streams: один метод на строку, filter перед map
</java>

<other-languages>
Для языков вне основного скоупа (TypeScript, Rust, C++, Ruby и др.):
1. Прочитай существующий код в репозитории
2. Определи конвенции по паттернам:
   - Стиль именования (camelCase, snake_case, etc.)
   - Структура файлов и модулей
   - Обработка ошибок
3. Следуй принципам:
   - Консистентность с существующим кодом
   - Файлы заканчиваются newline
   - Читаемость важнее краткости
4. При неопределённости — укажи это в описании изменений
</other-languages>
</language-conventions>

<anti-patterns>
- НЕ создавай файлы без необходимости
- НЕ добавляй комментарии к неизменённому коду
- НЕ используй util/common/misc в именах пакетов/модулей
- НЕ игнорируй ошибки — обрабатывай их явно
- НЕ делай "улучшения" за пределами задачи
</anti-patterns>

<response-format>
- Объясни решение ПЕРЕД внесением изменений
- Используй инструменты для работы с кодом
- Отвечай кратко и по делу
- Отвечай на русском языке
</response-format>
"""


class CodeAgent:
    """Agent that generates code changes based on Issues."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        model: str | None = None,
    ):
        settings = get_settings()
        self.github = github_client or GitHubClient()
        self.model = model or settings.default_model
        self.api_key = settings.llm_api_key
        self.max_iterations = settings.max_iterations

    def process_issue(self, issue_number: int) -> dict:
        """Process an issue and create a PR with changes.

        Returns:
            dict with keys: success, pr_number, branch, message
        """
        # Get issue data
        issue = self.github.get_issue(issue_number)

        # Create branch for changes
        branch_name = f"issue-{issue_number}-auto"
        self.github.create_branch(branch_name)

        # Create tools with branch context
        tools = create_code_tools(self.github, branch_name)

        # Create agent
        agent = Agent(
            model=OpenRouter(id=self.model, api_key=self.api_key),
            tools=tools,
            instructions=CODE_AGENT_PROMPT,
            markdown=True,
        )

        # Build prompt with issue context
        prompt = self._build_prompt(issue)

        # Run agent
        try:
            response = agent.run(prompt)

            # Create PR
            pr_number = self.github.create_pull_request(
                title=f"Fix #{issue_number}: {issue.title}",
                body=self._create_pr_body(issue, response.content),
                head=branch_name,
            )

            return {
                "success": True,
                "pr_number": pr_number,
                "branch": branch_name,
                "message": "PR created successfully",
            }
        except Exception as e:
            return {
                "success": False,
                "pr_number": None,
                "branch": branch_name,
                "message": f"Error: {str(e)}",
            }

    def _build_prompt(self, issue: IssueData) -> str:
        """Build prompt for the agent."""
        return f"""<task>
Реализуй Issue #{issue.number}: {issue.title}
</task>

<requirements>
{issue.body}
</requirements>

<tools-sequence>
Вызови tools В ЭТОМ ПОРЯДКЕ:

1. list_files() — изучи структуру проекта
2. read_file(path) — прочитай релевантные файлы
3. write_file(path, content, message) — внеси изменения
4. check_python_style(path) — для .py файлов проверь стиль
5. validate_all_python_files() — финальная проверка Python проекта
</tools-sequence>

<reminder>
- Определи язык проекта по файлам и следуй его конвенциям
- Делай минимальные изменения для решения задачи
- Файлы должны заканчиваться newline
</reminder>

Действуй!
"""

    def _create_pr_body(self, issue: IssueData, agent_response: str) -> str:
        """Create PR description."""
        return f"""## Summary
Automated fix for #{issue.number}

## Related Issue
Closes #{issue.number}

## Changes Made
{agent_response[:1000]}...

---
🤖 *Generated by **Code Agent***
"""

    def apply_review_feedback(
        self,
        pr_number: int,
        feedback: str,
        branch: str,
    ) -> dict:
        """Apply changes based on reviewer feedback.

        Returns:
            dict with keys: success, message
        """
        # Create tools with branch context
        tools = create_code_tools(self.github, branch)

        # Create agent
        agent = Agent(
            model=OpenRouter(id=self.model, api_key=self.api_key),
            tools=tools,
            instructions=CODE_AGENT_PROMPT,
            markdown=True,
        )

        prompt = f"""Ревьюер запросил изменения в PR #{pr_number}.

## Фидбек ревьюера:
{feedback}

## Твоя задача:
1. Прочитай файлы, которые нужно исправить
2. Пойми ПРИЧИНУ замечаний (не симптомы)
3. Внеси минимальные точечные исправления
4. Проверь стиль через check_python_style
5. Убедись что все файлы валидны через validate_all_python_files

## Напоминания:
- Python файлы должны заканчиваться на \\n
- Импорты: stdlib → third-party → local
- Максимум 3 попытки на одну ошибку

Действуй!
"""

        try:
            response = agent.run(prompt)

            # Add comment to PR
            self.github.add_pr_comment(
                pr_number,
                f"🤖 **Code Agent** — исправления по фидбеку:\n\n{response.content[:500]}...",
            )

            return {
                "success": True,
                "message": "Feedback addressed",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}",
            }
