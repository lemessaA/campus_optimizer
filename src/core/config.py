# src/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://postgres:qaws@localhost:5432/campus"
    REDIS_URL: str = "redis://localhost:6379"
    
    # Agent Settings
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: float = 2.0
    AGENT_TIMEOUT: int = 30
    MAX_ITERATIONS: int = 10
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"

    # LLM
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GROQ_TEMPERATURE: float = 0.7
    LLM_TIMEOUT: int = 30  # seconds for LLM API calls

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "DeepSeek-R1"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TEMPERATURE: float = 0.7
    
    # Logging
    LOG_LEVEL: str = "INFO"

    # Environment (development, staging, production)
    ENVIRONMENT: str = "development"

    # Optional: PagerDuty key for critical alerts (monitoring_advanced)
    PAGERDUTY_KEY: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()