"""Tests for configuration."""

import os
import pytest


def test_settings_defaults():
    """Test default settings values."""
    # Clear env vars for test
    env_backup = {}
    for key in ["LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL"]:
        env_backup[key] = os.environ.pop(key, None)

    try:
        from src.core.config import Settings

        settings = Settings()
        assert settings.llm_provider == "openrouter"
        assert settings.max_iterations == 5
    finally:
        # Restore env vars
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value


def test_settings_base_url():
    """Test base URL generation for providers."""
    from src.core.config import Settings

    settings = Settings(llm_provider="openrouter")
    assert "openrouter" in settings.llm_base_url

    settings = Settings(llm_provider="groq")
    assert "groq" in settings.llm_base_url


def test_settings_default_model():
    """Test default model selection."""
    from src.core.config import Settings

    settings = Settings(llm_provider="openrouter", llm_model="")
    assert settings.default_model == "google/gemini-2.5-flash"

    settings = Settings(llm_provider="openrouter", llm_model="custom/model")
    assert settings.default_model == "custom/model"
