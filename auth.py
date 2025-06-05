import jwt
import redis
import httpx
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings
import json
import time

redis_client = redis.from_url(settings.REDIS_URL)
security = HTTPBearer()

class AuthManager:
    def __init__(self):
        self.keycloak_public_key = None
        self.last_key_fetch = 0
        
    async def get_keycloak_public_key(self):
        """Fetch Keycloak public key for JWT verification"""
        current_time = time.time()
        if self.keycloak_public_key and (current_time - self.last_key_fetch) < 3600:
            return self.keycloak_public_key
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid_connect/certs"
                )
                keys = response.json()["keys"][0]
                
                # Convert JWK to PEM format (simplified)
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import rsa
                
                # This is a simplified version - in production, use proper JWK to PEM conversion
                self.keycloak_public_key = keys
                self.last_key_fetch = current_time
                return self.keycloak_public_key
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch Keycloak public key: {str(e)}")
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token"""
        try:
            # Check if token is revoked
            if redis_client.sismember("revoked_tokens", token):
                raise HTTPException(status_code=401, detail="Token has been revoked")
            
            # Decode JWT token
            # In production, use proper key verification with Keycloak's public key
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_signature": False}  # Simplified for demo
            )
            
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    async def check_permissions(self, user_payload: Dict[str, Any], required_roles: List[str]) -> bool:
        """Check if user has required roles"""
        user_roles = user_payload.get("realm_access", {}).get("roles", [])
        return any(role in user_roles for role in required_roles)
    
    async def check_resource_ownership(self, user_payload: Dict[str, Any], resource_id: str) -> bool:
        """Check if user owns the requested resource"""
        user_id = user_payload.get("sub") or user_payload.get("user_id")
        return str(user_id) == str(resource_id)
    
    def revoke_token(self, token: str):
        """Add token to revocation list"""
        redis_client.sadd("revoked_tokens", token)
        # Set expiration based on token's exp claim
        redis_client.expire("revoked_tokens", 86400)  # 24 hours

auth_manager = AuthManager()

async def get_current_user(credentials: HTTPAuthorizationCredentials = security):
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    return await auth_manager.verify_token(token)

def check_ip_whitelist(request: Request):
    """Check if request IP is whitelisted"""
    client_ip = request.client.host
    if client_ip not in settings.ALLOWED_IPS and "0.0.0.0" not in settings.ALLOWED_IPS:
        raise HTTPException(status_code=403, detail="IP address not allowed")
