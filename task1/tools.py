# tools.py
"""Инструменты агента для работы с файлами"""

import os
from langchain_core.tools import tool


@tool
def list_files(directory: str = ".") -> str:
    """Показывает список файлов в директории.

    Args:
        directory: Путь к директории
    """
    try:
        files = []
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in filenames:
                if not f.startswith('.'):
                    files.append(os.path.join(root, f))
        return "\n".join(files) if files else "Директория пуста"
    except Exception as e:
        return f"Ошибка: {e}"


@tool
def read_file(filepath: str) -> str:
    """Читает содержимое файла.

    Args:
        filepath: Путь к файлу
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"Файл не найден: {filepath}"
    except Exception as e:
        return f"Ошибка: {e}"


@tool
def write_file(filepath: str, content: str) -> str:
    """Записывает содержимое в файл.

    Args:
        filepath: Путь к файлу
        content: Содержимое
    """
    try:
        if os.path.dirname(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Файл {filepath} сохранён"
    except Exception as e:
        return f"Ошибка: {e}"


def get_tools():
    """Возвращает список инструментов"""
    return [list_files, read_file, write_file]
