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
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()