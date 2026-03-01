# src/services/retry.py
import asyncio
import time
from src.services.monitoring import logger

def with_retry(max_retries: int = 3, backoff_factor: float = 2.0):
    """Retry decorator for async functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    delay = backoff_factor * (2 ** (retries - 1))
                    logger.error(f"Retry {retries}/{max_retries} failed: {str(e)}")
                    await asyncio.sleep(delay)
            raise Exception(f"Max retries ({max_retries}) exceeded")
        return wrapper
    return decorator
    