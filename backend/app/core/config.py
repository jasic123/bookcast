"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    # Application
    APP_NAME: str = "Book Podcast Research"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./book_research.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Tavily API
    TAVILY_API_KEY: str = ""

    # LLM API (OpenAI compatible)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7

    # Search settings
    MAX_SEARCH_RESULTS_PER_QUERY: int = 10
    MAX_SEARCH_RETRIES: int = 3
    SEARCH_TIMEOUT_SECONDS: int = 30

    # Resource limits
    MAX_BOOKS_PER_LIST: int = 100
    MAX_CONCURRENT_SEARCHES: int = 5
    MAX_TASK_EXECUTION_TIME: int = 600

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
