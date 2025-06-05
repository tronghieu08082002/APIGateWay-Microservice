import os
from typing import List, Dict, Any
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Authentication
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "master")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "RS256"
    
    # Security
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,https://yourdomain.com").split(",")
    ALLOWED_IPS: List[str] = os.getenv("ALLOWED_IPS", "127.0.0.1,::1").split(",")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
    PREMIUM_RATE_LIMIT: int = int(os.getenv("PREMIUM_RATE_LIMIT", "1000"))
    
    # Payload
    MAX_PAYLOAD_SIZE: int = int(os.getenv("MAX_PAYLOAD_SIZE", "10485760"))  # 10MB
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
    
    # Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60"))
    
    # Microservices
    MICROSERVICES: Dict[str, Any] = {
        "user-service": {
            "urls": os.getenv("USER_SERVICE_URLS", "http://localhost:8001,http://localhost:8002").split(","),
            "health_check": "/health"
        },
        "order-service": {
            "urls": os.getenv("ORDER_SERVICE_URLS", "http://localhost:8003").split(","),
            "health_check": "/health"
        }
    }
    
    class Config:
        env_file = ".env"

settings = Settings()
