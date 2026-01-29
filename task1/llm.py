# llm.py
"""Работа с LLM"""

from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL



def get_llm():
    """Создаёт LLM клиент"""
    return ChatOpenAI(
        model=MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )


def chat(user_message: str) -> str:
    """Простой чат с LLM"""
    llm = get_llm()
    response = llm.invoke(user_message)
    return response.content


SYSTEM_PROMPT = """Ты - coding agent, помощник программиста.

Твои возможности:
- list_files: посмотреть файлы в директории
- read_file: прочитать содержимое файла
- write_file: записать/изменить файл

Правила:
1. Сначала изучи структуру проекта через list_files
2. Читай файлы перед изменением
3. Объясняй что делаешь
4. Пиши ПОЛНОЕ содержимое файла при изменении

Отвечай на русском языке.
"""
