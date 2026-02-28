# src/services/cache.py
import redis.asyncio as redis
from src.core.config import settings
from typing import Optional, Any
import json

redis_client: Optional[redis.Redis] = None

async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def close_redis():
    """Close Redis connection"""
    if redis_client:
        await redis_client.close()

async def check_redis_connection() -> bool:
    """Check Redis connection health"""
    try:
        await redis_client.ping()
        return True
    except:
        return False

# Cache decorator
def cache(ttl_seconds: int = 300):
    """Cache decorator for functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await redis_client.setex(cache_key, ttl_seconds, json.dumps(result))
            
            return result
        return wrapper
    return decorator