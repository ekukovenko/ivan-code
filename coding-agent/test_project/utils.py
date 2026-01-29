# utils.py
"""
Вспомогательные функции для калькулятора
"""


def validate_number(value):
    """Проверяет, является ли значение числом"""
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def format_result(operation, a, b, result):
    """Форматирует результат операции для вывода"""
    return f"{a} {operation} {b} = {result}"


def safe_input(prompt):
    """Безопасный ввод числа от пользователя"""
    while True:
        try:
            value = input(prompt)
            return float(value)
        except ValueError:
            print("Ошибка: введите число!")
