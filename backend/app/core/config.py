"""
Central configuration loaded from environment variables / .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URI: str = os.getenv("DATABASE_URI", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1")
    FAST_LLM_MODEL: str = os.getenv("FAST_LLM_MODEL", "gpt-4.1-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    # CORS – comma-separated origins, e.g. "http://localhost:5500,https://yourapp.com"
    ALLOWED_ORIGINS: list[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")


settings = Settings()
