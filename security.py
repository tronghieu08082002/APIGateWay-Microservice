import json
import gzip
from typing import Dict, Any, List
from fastapi import Response
from fastapi.responses import JSONResponse

class SecurityManager:
    def __init__(self):
        self.sensitive_fields = [
            "password", "token_secret", "internal_flag", "secret_key",
            "private_key", "api_key", "auth_token", "session_id"
        ]
        
        self.security_headers = {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
    
    def filter_sensitive_data(self, data: Any) -> Any:
        """Remove sensitive fields from response data"""
        if isinstance(data, dict):
            filtered_data = {}
            for key, value in data.items():
                if key.lower() not in self.sensitive_fields:
                    filtered_data[key] = self.filter_sensitive_data(value)
            return filtered_data
        elif isinstance(data, list):
            return [self.filter_sensitive_data(item) for item in data]
        else:
            return data
    
    def add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        for header, value in self.security_headers.items():
            response.headers[header] = value
        return response
    
    def compress_response(self, content: bytes) -> bytes:
        """Compress response content using gzip"""
        return gzip.compress(content)
    
    def transform_request_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Transform request headers before forwarding"""
        # Remove potentially dangerous headers
        dangerous_headers = ["x-forwarded-for", "x-real-ip"]
        filtered_headers = {k: v for k, v in headers.items() 
                          if k.lower() not in dangerous_headers}
        
        # Add custom headers
        filtered_headers["X-Gateway-Version"] = "1.0"
        filtered_headers["X-Request-ID"] = "generated-request-id"
        
        return filtered_headers

security_manager = SecurityManager()
