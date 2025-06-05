import redis
import time
import httpx
from typing import Dict, List
from enum import Enum
from config import settings

redis_client = redis.from_url(settings.REDIS_URL)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self):
        self.redis = redis_client
    
    def get_circuit_state(self, service_name: str) -> CircuitState:
        """Get current circuit breaker state for a service"""
        state = self.redis.hget(f"circuit:{service_name}", "state")
        if not state:
            return CircuitState.CLOSED
        return CircuitState(state.decode())
    
    def record_success(self, service_name: str):
        """Record successful request"""
        pipe = self.redis.pipeline()
        pipe.hset(f"circuit:{service_name}", "state", CircuitState.CLOSED.value)
        pipe.hdel(f"circuit:{service_name}", "failure_count", "last_failure_time")
        pipe.execute()
    
    def record_failure(self, service_name: str):
        """Record failed request"""
        current_time = int(time.time())
        pipe = self.redis.pipeline()
        
        # Increment failure count
        pipe.hincrby(f"circuit:{service_name}", "failure_count", 1)
        pipe.hset(f"circuit:{service_name}", "last_failure_time", current_time)
        
        results = pipe.execute()
        failure_count = int(self.redis.hget(f"circuit:{service_name}", "failure_count") or 0)
        
        # Open circuit if failure threshold exceeded
        if failure_count >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            self.redis.hset(f"circuit:{service_name}", "state", CircuitState.OPEN.value)
    
    def can_attempt_request(self, service_name: str) -> bool:
        """Check if request can be attempted"""
        state = self.get_circuit_state(service_name)
        
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            last_failure_time = self.redis.hget(f"circuit:{service_name}", "last_failure_time")
            if last_failure_time:
                time_since_failure = int(time.time()) - int(last_failure_time)
                if time_since_failure >= settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT:
                    # Move to half-open state
                    self.redis.hset(f"circuit:{service_name}", "state", CircuitState.HALF_OPEN.value)
                    return True
            return False
        elif state == CircuitState.HALF_OPEN:
            return True
        
        return False

circuit_breaker = CircuitBreaker()
