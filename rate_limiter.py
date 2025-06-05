import redis
import time
from typing import Optional
from fastapi import HTTPException, Request
from config import settings

redis_client = redis.from_url(settings.REDIS_URL)

class RateLimiter:
    def __init__(self):
        self.redis = redis_client
    
    async def check_rate_limit(self, identifier: str, user_type: str = "regular") -> bool:
        """Check if request is within rate limits"""
        current_time = int(time.time())
        window_start = current_time - settings.RATE_LIMIT_WINDOW
        
        # Determine rate limit based on user type
        if user_type == "premium":
            max_requests = settings.PREMIUM_RATE_LIMIT
        else:
            max_requests = settings.RATE_LIMIT_REQUESTS
        
        # Use sliding window rate limiting
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(f"rate_limit:{identifier}", 0, window_start)
        pipe.zcard(f"rate_limit:{identifier}")
        pipe.zadd(f"rate_limit:{identifier}", {str(current_time): current_time})
        pipe.expire(f"rate_limit:{identifier}", settings.RATE_LIMIT_WINDOW)
        
        results = pipe.execute()
        current_requests = results[1]
        
        if current_requests >= max_requests:
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit exceeded. Max {max_requests} requests per {settings.RATE_LIMIT_WINDOW} seconds"
            )
        
        return True
    
    async def get_user_quota_info(self, user_id: str) -> dict:
        """Get user quota information from Redis"""
        quota_key = f"user_quota:{user_id}"
        quota_info = self.redis.hgetall(quota_key)
        
        if not quota_info:
            # Default quota for regular users
            return {"type": "regular", "requests_used": 0, "requests_limit": settings.RATE_LIMIT_REQUESTS}
        
        return {
            "type": quota_info.get(b"type", b"regular").decode(),
            "requests_used": int(quota_info.get(b"requests_used", 0)),
            "requests_limit": int(quota_info.get(b"requests_limit", settings.RATE_LIMIT_REQUESTS))
        }

rate_limiter = RateLimiter()
