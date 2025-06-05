import random
import hashlib
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
from config import settings

class LoadBalancer:
    def __init__(self):
        self.current_index = {}
    
    def round_robin(self, service_name: str, urls: List[str]) -> str:
        """Round-robin load balancing"""
        if service_name not in self.current_index:
            self.current_index[service_name] = 0
        
        url = urls[self.current_index[service_name]]
        self.current_index[service_name] = (self.current_index[service_name] + 1) % len(urls)
        return url
    
    def random_selection(self, urls: List[str]) -> str:
        """Random load balancing"""
        return random.choice(urls)
    
    def get_service_url(self, service_name: str, strategy: str = "round_robin") -> Optional[str]:
        """Get service URL based on load balancing strategy"""
        service_config = settings.MICROSERVICES.get(service_name)
        if not service_config:
            return None
        
        urls = service_config["urls"]
        if not urls:
            return None
        
        if strategy == "round_robin":
            return self.round_robin(service_name, urls)
        elif strategy == "random":
            return self.random_selection(urls)
        else:
            return urls[0]

class RequestRouter:
    def __init__(self):
        self.load_balancer = LoadBalancer()
    
    def determine_service(self, path: str, method: str, headers: Dict[str, str], query_params: Dict[str, Any]) -> Optional[str]:
        """Determine which microservice should handle the request"""
        
        # Path-based routing
        if path.startswith("/api/user"):
            return "user-service"
        elif path.startswith("/api/order"):
            return "order-service"
        
        # Header-based routing
        service_type = headers.get("X-Service-Type")
        if service_type in settings.MICROSERVICES:
            return service_type
        
        # Query parameter-based routing
        region = query_params.get("region")
        if region == "us":
            return "user-service"  # Example routing logic
        
        return None
    
    def get_target_url(self, service_name: str, path: str) -> Optional[str]:
        """Get the target URL for the request"""
        base_url = self.load_balancer.get_service_url(service_name)
        if not base_url:
            return None
        
        return f"{base_url.rstrip('/')}{path}"

router = RequestRouter()
