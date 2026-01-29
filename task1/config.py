# config.py
"""Конфигурация"""

import os

import dotenv
dotenv.load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # Для OpenRouter: https://openrouter.ai/api/v1
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini")
DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")
