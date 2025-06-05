import httpx
import json
import time
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from urllib.parse import parse_qs
import uvicorn

from config import settings
from auth import auth_manager, get_current_user, check_ip_whitelist
from rate_limiter import rate_limiter
from circuit_breaker import circuit_breaker
from router import router
from security import security_manager
from cache import cache_manager

app = FastAPI(
    title="API Gateway",
    description="Secure API Gateway with authentication, rate limiting, and routing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Security middleware for IP filtering and payload size checking"""
    
    # Check IP whitelist
    try:
        check_ip_whitelist(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    # Check payload size
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > settings.MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=413, 
                content={"detail": "Payload too large"}
            )
    
    response = await call_next(request)
    
    # Add security headers
    response = security_manager.add_security_headers(response)
    
    return response

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/auth/revoke")
async def revoke_token(request: Request, current_user: dict = Depends(get_current_user)):
    """Revoke JWT token"""
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        auth_manager.revoke_token(token)
        return {"message": "Token revoked successfully"}
    
    raise HTTPException(status_code=400, detail="Invalid token")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway_handler(request: Request, path: str, current_user: dict = Depends(get_current_user)):
    """Main gateway handler for all requests"""
    
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    
    # Rate limiting
    user_id = current_user.get("sub") or current_user.get("user_id")
    user_quota = await rate_limiter.get_user_quota_info(user_id)
    
    try:
        await rate_limiter.check_rate_limit(
            identifier=f"user:{user_id}",
            user_type=user_quota["type"]
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    # Determine target service
    service_name = router.determine_service(f"/{path}", method, headers, query_params)
    if not service_name:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Check permissions based on path
    required_roles = []
    if path.startswith("api/admin"):
        required_roles = ["admin"]
    elif path.startswith("api/user"):
        required_roles = ["user", "admin"]
    
    if required_roles and not await auth_manager.check_permissions(current_user, required_roles):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check resource ownership for user-specific endpoints
    if "/api/user/" in path and path.count("/") >= 3:
        path_parts = path.split("/")
        if len(path_parts) >= 4:
            resource_id = path_parts[3]
            if not await auth_manager.check_resource_ownership(current_user, resource_id):
                raise HTTPException(status_code=403, detail="Access denied: resource ownership check failed")
    
    # Check cache for GET requests
    cache_key = None
    if cache_manager.should_cache_request(method, f"/{path}"):
        cache_key = cache_manager.generate_cache_key(
            method, f"/{path}", str(query_params), user_id
        )
        cached_response = await cache_manager.get_cached_response(cache_key)
        if cached_response:
            return JSONResponse(content=cached_response)
    
    # Circuit breaker check
    if not circuit_breaker.can_attempt_request(service_name):
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    
    # Get target URL
    target_url = router.get_target_url(service_name, f"/{path}")
    if not target_url:
        raise HTTPException(status_code=502, detail="Service unavailable")
    
    # Prepare request
    request_headers = security_manager.transform_request_headers(headers)
    request_body = None
    
    if method in ["POST", "PUT", "PATCH"]:
        request_body = await request.body()
    
    # Forward request to microservice
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=target_url,
                headers=request_headers,
                params=query_params,
                content=request_body
            )
        
        # Record success for circuit breaker
        circuit_breaker.record_success(service_name)
        
        # Process response
        response_data = None
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                response_data = response.json()
                # Filter sensitive data
                response_data = security_manager.filter_sensitive_data(response_data)
            except:
                response_data = {"message": "Invalid JSON response"}
        else:
            response_data = {"content": response.text}
        
        # Cache successful GET responses
        if cache_key and response.status_code == 200:
            await cache_manager.cache_response(cache_key, response_data)
        
        return JSONResponse(
            content=response_data,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
        
    except httpx.RequestError as e:
        # Record failure for circuit breaker
        circuit_breaker.record_failure(service_name)
        raise HTTPException(status_code=502, detail=f"Service request failed: {str(e)}")
    except httpx.TimeoutException:
        circuit_breaker.record_failure(service_name)
        raise HTTPException(status_code=504, detail="Service request timeout")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=True
    )
