"""Reviewer Agent - analyzes PRs and provides code review.

IMPORTANT: This agent is ISOLATED from Code Agent.
It acts as an independent, critical reviewer.
"""

from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from src.core.config import get_settings
from src.github.client import GitHubClient
from src.tools.review_tools import create_review_tools


REVIEWER_AGENT_PROMPT = """<role>
Ты — строгий и независимый код-ревьюер. Твоя задача — критически анализировать Pull Request и обеспечивать качество кода.
</role>

<principles>
- Ты НЕЗАВИСИМ от автора кода — не одобряй автоматически
- НИКОГДА не выдумывай проблемы — анализируй только реальный код
- Будь конкретен — указывай файлы и строки при замечаниях
- Фокусируйся на БЛОКИРУЮЩИХ проблемах, не придирайся к мелочам
</principles>

<checklist>
1. **Соответствие требованиям**: Код решает задачу из issue?
2. **Качество кода**: Читаемый, идиоматичный, поддерживаемый?
3. **Баги**: Логические ошибки, необработанные edge cases?
4. **Безопасность**: Вызови security_check_pr() для проверки уязвимостей!
5. **Стиль**: Соответствует конвенциям языка и проекта?
</checklist>

<language-checks>
<python>
- W292: trailing newline в конце файла
- I001: порядок импортов (stdlib → third-party → local)
- Синтаксис и типизация
</python>

<go>
- gofmt соответствие
- Обработка ВСЕХ ошибок (нет _ для игнорирования)
- Нейминг: MixedCaps без underscores
- Короткие имена ресиверов
</go>

<kotlin>
- Null safety: избегать !! (использовать ?. и ?:)
- Идиоматичный Kotlin (не Java-style код)
- val вместо var где возможно
- Coroutines вместо callbacks
</kotlin>

<java>
- Naming conventions (PascalCase, lowerCamelCase, UPPER_SNAKE_CASE)
- Optional только для return types
- Stream pipelines: один метод на строку
- Records для иммутабельных данных
</java>

<other-languages>
Для языков вне основного скоупа:
1. Проверь консистентность с существующим кодом
2. Убедись что trailing newline присутствует
3. Проверь базовую безопасность (инъекции, XSS)
4. Оцени читаемость и поддерживаемость
5. При невозможности оценить стиль — сфокусируйся на логике
</other-languages>
</language-checks>

<ci-rules>
- CI FAILING → обязательно REQUEST_CHANGES
- CI PENDING → подожди или отметь в комментарии
- CI SUCCESS → можно APPROVE если код корректен
</ci-rules>

<decisions>
- **APPROVE**: CI проходит И код корректно решает задачу
- **REQUEST_CHANGES**: Баги, проблемы безопасности, CI падает
- **COMMENT**: Есть предложения, но нет блокеров
</decisions>

<workflow>
1. Получи diff через get_pr_diff — пойми что изменилось
2. Проверь CI статус через get_ci_status
3. Прочитай требования issue через get_issue_requirements
4. Вызови security_check_pr() — проверь на уязвимости
5. При необходимости прочитай полные файлы для контекста
6. **ОБЯЗАТЕЛЬНО** вызови submit_review с решением
</workflow>

⚠️ КРИТИЧНО: Ты ДОЛЖЕН вызвать submit_review в конце! Без этого ревью не будет отправлено.

<response-format>
Структурируй ответ:
- **Резюме**: Что делает PR (1-2 предложения)
- **CI статус**: Проходит/падает
- **Замечания**: Список проблем (если есть)
- **Решение**: APPROVE / REQUEST_CHANGES / COMMENT

Отвечай на русском языке.
</response-format>
"""


class ReviewerAgent:
    """Agent that reviews PRs independently from Code Agent."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        model: str | None = None,
    ):
        settings = get_settings()
        self.github = github_client or GitHubClient()
        self.model = model or settings.default_model
        self.api_key = settings.llm_api_key

    def review_pr(self, pr_number: int, issue_number: int | None = None) -> dict:
        """Review a pull request.

        Args:
            pr_number: PR number to review
            issue_number: Related issue number (optional)

        Returns:
            dict with keys: decision, summary, needs_changes
        """
        # Track if submit_review was called
        review_state = {"submitted": False, "decision": None}

        # Create tools with PR context and state tracking
        tools = create_review_tools(self.github, pr_number, review_state)

        # Create agent
        agent = Agent(
            model=OpenRouter(id=self.model, api_key=self.api_key),
            tools=tools,
            instructions=REVIEWER_AGENT_PROMPT,
            markdown=True,
        )

        # Build prompt
        prompt = self._build_prompt(pr_number, issue_number)

        try:
            response = agent.run(prompt)

            if review_state["submitted"]:
                # LLM called submit_review — use its decision
                decision = review_state["decision"]
            else:
                # LLM did NOT call submit_review — fallback: post review ourselves
                decision = self._parse_decision(response.content)
                self._fallback_post_review(pr_number, decision, response.content)

            return {
                "decision": decision,
                "summary": response.content,
                "needs_changes": decision == "REQUEST_CHANGES",
            }
        except Exception as e:
            return {
                "decision": "COMMENT",
                "summary": f"Review failed: {str(e)}",
                "needs_changes": True,
            }

    def _fallback_post_review(self, pr_number: int, decision: str, summary: str) -> None:
        """Post review to GitHub when LLM didn't call submit_review."""
        try:
            marked_summary = f"**Reviewer Agent** (fallback)\n\n{summary}"
            event = decision.upper()

            try:
                self.github.create_pr_review(
                    pr_number=pr_number,
                    body=marked_summary,
                    event=event,
                )
            except Exception as e:
                # GitHub doesn't allow approving own PRs
                if "approve your own" in str(e).lower() and event == "APPROVE":
                    marked_summary = f"**Reviewer Agent** APPROVED (fallback)\n\n{summary}\n\n---\n*Статус: APPROVE (отправлено как COMMENT из-за ограничений GitHub)*"
                    self.github.create_pr_review(
                        pr_number=pr_number,
                        body=marked_summary,
                        event="COMMENT",
                    )
        except Exception:
            pass  # Ignore fallback errors to not break the flow

    def _build_prompt(self, pr_number: int, issue_number: int | None) -> str:
        """Build review prompt."""
        issue_instruction = ""
        if issue_number:
            issue_instruction = f"""
3. Вызови get_issue_requirements({issue_number}) — сравни реализацию с требованиями"""
        else:
            issue_instruction = """
3. Пойми цель изменений из контекста diff"""

        return f"""<task>
Проведи code review для Pull Request #{pr_number}
</task>

<instructions>
Выполни шаги ПОСЛЕДОВАТЕЛЬНО, вызывая tools:

1. Вызови get_pr_diff() — получи и проанализируй изменения
2. Вызови get_ci_status() — проверь статус CI (если FAILING — это блокер){issue_instruction}
4. При необходимости вызови read_file(path) для полного контекста файлов
5. ⚠️ ОБЯЗАТЕЛЬНО вызови submit_review(decision, summary) с решением

БЕЗ ВЫЗОВА submit_review РЕВЬЮ НЕ БУДЕТ ОТПРАВЛЕНО!
</instructions>

<decision-guide>
- APPROVE: CI проходит И код корректно решает задачу
- REQUEST_CHANGES: баги, проблемы безопасности, CI падает, код не соответствует требованиям
- COMMENT: есть предложения по улучшению, но нет блокирующих проблем
</decision-guide>

Действуй!
"""

    def _parse_decision(self, response: str) -> str:
        """Parse decision from agent response."""
        response_upper = response.upper()
        if "REQUEST_CHANGES" in response_upper or "REQUEST CHANGES" in response_upper:
            return "REQUEST_CHANGES"
        elif "APPROVE" in response_upper and "NOT APPROVE" not in response_upper:
            return "APPROVE"
        return "COMMENT"
