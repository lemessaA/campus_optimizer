# src/core/rate_limiter.py
import time
from typing import Dict, Tuple, Optional
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
import redis.asyncio as redis
from src.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class RateLimiter:
    """Rate limiter using Redis"""
    
    def __init__(self):
        self.default_limits = {
            "anonymous": (100, 60),  # 100 requests per minute
            "authenticated": (1000, 60),  # 1000 requests per minute
            "support_ticket": (5, 86400),  # 5 tickets per day
            "equipment_booking": (10, 604800),  # 10 bookings per week
            "course_creation": (20, 86400),  # 20 courses per day (faculty)
        }
    
    async def check_rate_limit(
        self,
        key: str,
        limit_type: str,
        user_type: str = "authenticated"
    ) -> Tuple[bool, Dict]:
        """Check if request is within rate limit"""
        limit, window = self.default_limits.get(limit_type, self.default_limits[user_type])
        
        redis_key = f"ratelimit:{limit_type}:{key}"
        
        # Get current count
        current = await redis_client.get(redis_key)
        
        if not current:
            # First request in window
            await redis_client.setex(redis_key, window, "1")
            return True, {"limit": limit, "remaining": limit - 1, "reset": window}
        
        current_count = int(current)
        
        if current_count >= limit:
            # Rate limit exceeded
            ttl = await redis_client.ttl(redis_key)
            return False, {"limit": limit, "remaining": 0, "reset": ttl}
        
        # Increment count
        await redis_client.incr(redis_key)
        remaining = limit - (current_count + 1)
        
        return True, {"limit": limit, "remaining": remaining, "reset": await redis_client.ttl(redis_key)}
    
    async def get_rate_limit_headers(self, request: Request, user_id: Optional[str] = None) -> Dict:
        """Get rate limit headers for response"""
        # Determine key based on authentication
        if user_id:
            key = f"user:{user_id}"
            user_type = "authenticated"
        else:
            # Use IP for anonymous users
            key = f"ip:{request.client.host}"
            user_type = "anonymous"
        
        # Check general API rate limit
        allowed, info = await self.check_rate_limit(key, "api", user_type)
        
        return {
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset"])
        }

# Rate limiting middleware
from fastapi import FastAPI, Request
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.limiter = RateLimiter()
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get user ID if authenticated
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            # Verify token and get user ID
            from src.core.security import AuthService
            auth_service = AuthService()
            token_data = await auth_service.verify_token(token)
            if token_data:
                user_id = token_data.username
        
        # Check rate limit
        key = user_id or request.client.host
        allowed, info = await self.limiter.check_rate_limit(
            key,
            "api",
            "authenticated" if user_id else "anonymous"
        )
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests. Try again in {info['reset']} seconds"
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["reset"])
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response