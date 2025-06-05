import redis
import json
import hashlib
from typing import Optional, Any
from config import settings

redis_client = redis.from_url(settings.REDIS_URL)

class CacheManager:
    def __init__(self):
        self.redis = redis_client
        self.default_ttl = settings.CACHE_TTL
    
    def generate_cache_key(self, method: str, path: str, query_params: str, user_id: str = None) -> str:
        """Generate cache key for request"""
        key_data = f"{method}:{path}:{query_params}"
        if user_id:
            key_data += f":{user_id}"
        
        return f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def get_cached_response(self, cache_key: str) -> Optional[dict]:
        """Get cached response"""
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data.decode())
        except Exception:
            pass
        return None
    
    async def cache_response(self, cache_key: str, response_data: dict, ttl: int = None):
        """Cache response data"""
        try:
            ttl = ttl or self.default_ttl
            self.redis.setex(
                cache_key, 
                ttl, 
                json.dumps(response_data, default=str)
            )
        except Exception:
            pass  # Fail silently for cache errors
    
    def should_cache_request(self, method: str, path: str) -> bool:
        """Determine if request should be cached"""
        # Only cache GET requests
        if method.upper() != "GET":
            return False
        
        # Don't cache user-specific endpoints
        if "/api/user/" in path and path.count("/") > 2:
            return False
        
        # Cache public endpoints
        cacheable_patterns = ["/api/public/", "/api/config/", "/api/health"]
        return any(pattern in path for pattern in cacheable_patterns)

cache_manager = CacheManager()
