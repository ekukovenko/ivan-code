# logger.py
"""Логгер для Coding Agent"""

from enum import IntEnum
from config import DEBUG


class LogLevel(IntEnum):
    """Уровни логирования"""
    QUIET = 0    # Только ответы агента
    NORMAL = 1   # + вызовы инструментов (кратко)
    DEBUG = 2    # + детали вызовов и результаты


class Logger:
    """Красивый логгер для агента"""

    def __init__(self, level: LogLevel = None):
        if level is None:
            level = LogLevel.DEBUG if DEBUG else LogLevel.NORMAL
        self.level = level

    def agent(self, message: str):
        """Ответ агента - всегда показываем"""
        print(f"\n\033[1;32m Agent:\033[0m {message}")

    def tool_call(self, name: str, args: dict):
        """Вызов инструмента"""
        if self.level >= LogLevel.NORMAL:
            args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items())
            print(f"\033[33m   {name}\033[0m({args_str})")

    def tool_result(self, result: str):
        """Результат инструмента"""
        if self.level >= LogLevel.DEBUG:
            # preview = result[:200] + "..." if len(result) > 200 else result
            preview = result
            preview = preview.replace('\n', ' | ')
            print(f"\033[90m   -> {preview}\033[0m")

    def debug(self, message: str):
        """Отладочное сообщение"""
        if self.level >= LogLevel.DEBUG:
            print(f"\033[90m[debug] {message}\033[0m")

    def info(self, message: str):
        """Информационное сообщение"""
        print(f"\033[36m{message}\033[0m")

    def error(self, message: str):
        """Сообщение об ошибке"""
        print(f"\033[1;31m{message}\033[0m")

    def separator(self):
        """Разделитель"""
        print("\033[90m" + "-" * 50 + "\033[0m")


# Глобальный логгер
log = Logger()
