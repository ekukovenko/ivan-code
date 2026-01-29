# config.py
"""Конфигурация"""

import os
import dotenv

dotenv.load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENAI_API_KEY")  # OpenRouter API ключ
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
