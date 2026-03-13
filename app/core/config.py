"""
Application Configuration - Environment Variables & Settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Intelligent Code Review Bot"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # GitHub App
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_APP_INSTALLATION_ID: str = ""

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.1

    # LangChain
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "code-review-bot"

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = ""

    # Review Configuration
    MAX_FILES_PER_PR: int = 50
    MAX_DIFF_LINES: int = 2000
    REVIEW_TIMEOUT_SECONDS: int = 120
    MIN_SEVERITY_TO_BLOCK: str = "HIGH"  # LOW, MEDIUM, HIGH, CRITICAL

    # Feature Flags
    ENABLE_SECURITY_CHECKS: bool = True
    ENABLE_PERFORMANCE_CHECKS: bool = True
    ENABLE_STYLE_CHECKS: bool = True
    ENABLE_PR_SUMMARY: bool = True
    AUTO_APPROVE_MINOR: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
