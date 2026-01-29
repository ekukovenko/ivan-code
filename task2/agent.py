# agent.py
"""Coding Agent на базе Agno"""

import re
import os
from typing import AsyncIterator, Any
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools

from config import OPENROUTER_API_KEY, MODEL


SYSTEM_PROMPT = """Ты - coding agent, помощник программиста.

Твои возможности:
- Работа с файлами: читать, писать, список файлов
- Выполнение shell команд

Правила:
1. Сначала изучи структуру проекта
2. Читай файлы перед изменением
3. Объясняй что делаешь
4. Пиши ПОЛНОЕ содержимое файла при изменении

Отвечай на русском языке.
"""

# Глобальный агент для сохранения контекста
_agent: Agent | None = None


def get_agent() -> Agent:
    """Возвращает или создаёт агента"""
    global _agent
    if _agent is None:
        _agent = Agent(
            model=OpenRouter(id=MODEL, api_key=OPENROUTER_API_KEY),
            tools=[
                FileTools(),      # read_file, save_file, list_files
                ShellTools(),     # run_shell_command
            ],
            instructions=SYSTEM_PROMPT,
            markdown=True,
        )
    return _agent


def parse_file_mentions(message: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Парсит упоминания файлов в формате @path/to/file.py
    Возвращает (сообщение без @mentions, список (путь, содержимое))
    """
    pattern = r'@([\w./\-_]+\.\w+)'
    mentions = re.findall(pattern, message)

    files_content: list[tuple[str, str]] = []
    for filepath in mentions:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                files_content.append((filepath, content))
            except Exception as e:
                files_content.append((filepath, f"[Ошибка чтения: {e}]"))
        else:
            files_content.append((filepath, "[Файл не найден]"))

    return message, files_content


def build_message_with_context(message: str, files: list[tuple[str, str]]) -> str:
    """Собирает сообщение с контекстом файлов"""
    if not files:
        return message

    context_parts = [message, "\n\n--- Содержимое упомянутых файлов ---\n"]
    for filepath, content in files:
        context_parts.append(f"\n### {filepath}\n```\n{content}\n```\n")

    return "".join(context_parts)


async def run_agent_stream(user_message: str) -> AsyncIterator[Any]:
    """Запускает агента со стримингом"""
    # Парсим file mentions
    message, files = parse_file_mentions(user_message)
    full_message = build_message_with_context(message, files)

    agent = get_agent()
    async for chunk in agent.arun(full_message, stream=True):
        yield chunk


def run_agent(user_message: str) -> str:
    """Запускает агента (синхронно)"""
    message, files = parse_file_mentions(user_message)
    full_message = build_message_with_context(message, files)

    agent = get_agent()
    response = agent.run(full_message)
    return response.content
