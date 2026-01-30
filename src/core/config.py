"""Configuration for SDLC Agent.

Simple config via environment variables.
Jury can change provider by setting:
    - LLM_PROVIDER: openrouter | openai | groq | mistral
    - LLM_API_KEY: API key for the provider
    - LLM_MODEL: Model name (optional)
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # owner/repo format

# Webhook Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Agent Configuration
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))
CI_WAIT_TIMEOUT = int(os.getenv("CI_WAIT_TIMEOUT", "300"))  # seconds, 0 = no wait

# LangFuse Configuration (optional, for observability)
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


# Provider URLs (OpenAI-compatible)
BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
}

# Default models per provider
DEFAULT_MODELS = {
    "openrouter": "google/gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "mistral": "mistral-small-latest",
}


def get_base_url() -> str:
    """Get base URL for current provider."""
    return BASE_URLS.get(LLM_PROVIDER, BASE_URLS["openrouter"])


def get_model() -> str:
    """Get model name (custom or default for provider)."""
    if LLM_MODEL:
        return LLM_MODEL
    return DEFAULT_MODELS.get(LLM_PROVIDER, DEFAULT_MODELS["openrouter"])


# For backward compatibility
class Settings:
    """Simple settings wrapper."""

    @property
    def llm_provider(self) -> str:
        return LLM_PROVIDER

    @property
    def llm_api_key(self) -> str:
        return LLM_API_KEY

    @property
    def llm_base_url(self) -> str:
        return get_base_url()

    @property
    def default_model(self) -> str:
        return get_model()

    @property
    def github_token(self) -> str:
        return GITHUB_TOKEN

    @property
    def github_repo(self) -> str:
        return GITHUB_REPO

    @property
    def webhook_secret(self) -> str:
        return WEBHOOK_SECRET

    @property
    def max_iterations(self) -> int:
        return MAX_ITERATIONS

    @property
    def ci_wait_timeout(self) -> int:
        return CI_WAIT_TIMEOUT

    @property
    def langfuse_enabled(self) -> bool:
        return LANGFUSE_ENABLED

    @property
    def langfuse_public_key(self) -> str:
        return LANGFUSE_PUBLIC_KEY

    @property
    def langfuse_secret_key(self) -> str:
        return LANGFUSE_SECRET_KEY

    @property
    def langfuse_host(self) -> str:
        return LANGFUSE_HOST


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
