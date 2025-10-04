import time
import uuid
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
import json

class RequestResponseMiddleware(BaseHTTPMiddleware):
    """Middleware for logging and monitoring request/response cycles"""
    
    def __init__(self, app, enable_metrics: bool = True, enable_logging: bool = True):
        super().__init__(app)
        self.enable_metrics = enable_metrics
        self.enable_logging = enable_logging
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time': 0.0,
            'endpoints': {}
        }
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request (disabled)
        
        # Update metrics
        if self.enable_metrics:
            self.metrics['total_requests'] += 1
            endpoint = f"{request.method} {request.url.path}"
            if endpoint not in self.metrics['endpoints']:
                self.metrics['endpoints'][endpoint] = {
                    'count': 0,
                    'total_time': 0.0,
                    'success_count': 0,
                    'error_count': 0
                }
            self.metrics['endpoints'][endpoint]['count'] += 1
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Update metrics
            if self.enable_metrics:
                self.metrics['successful_requests'] += 1
                self.metrics['total_response_time'] += response_time
                self.metrics['endpoints'][endpoint]['total_time'] += response_time
                self.metrics['endpoints'][endpoint]['success_count'] += 1
            
            # Add response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = str(response_time)
            
            # Log response (disabled)
            
            return response
            
        except Exception as e:
            # Calculate response time
            response_time = time.time() - start_time
            
            # Update metrics
            if self.enable_metrics:
                self.metrics['failed_requests'] += 1
                self.metrics['total_response_time'] += response_time
                self.metrics['endpoints'][endpoint]['total_time'] += response_time
                self.metrics['endpoints'][endpoint]['error_count'] += 1
            
            # Log error (disabled)
            
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        if not self.enable_metrics:
            return {"metrics_disabled": True}
        
        avg_response_time = (
            self.metrics['total_response_time'] / self.metrics['total_requests']
            if self.metrics['total_requests'] > 0 else 0
        )
        
        return {
            **self.metrics,
            'average_response_time': avg_response_time,
            'success_rate': (
                self.metrics['successful_requests'] / self.metrics['total_requests']
                if self.metrics['total_requests'] > 0 else 0
            )
        }
    
    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time': 0.0,
            'endpoints': {}
        }

class CircuitBreakerState:
    """Circuit breaker states"""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit is open, requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service is back

class CircuitBreaker:
    """Circuit breaker pattern implementation for LLM providers"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        
        # Circuit breaker initialized
    
    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                # Circuit breaker transitioning to HALF_OPEN state
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return (
            datetime.now() - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout
    
    def record_success(self):
        """Record a successful execution"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        # Circuit breaker recorded success, state reset to CLOSED
    
    def record_failure(self):
        """Record a failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            # Circuit breaker opened after failures
        else:
            # Circuit breaker failure count
            pass
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'can_execute': self.can_execute()
        }

class CircuitBreakerMiddleware:
    """Middleware for applying circuit breaker pattern to LLM calls"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = {
            'failure_threshold': 3,
            'recovery_timeout': 30,
            'expected_exception': Exception
        }
    
    def get_circuit_breaker(self, provider_name: str, config: Optional[Dict] = None) -> CircuitBreaker:
        """Get or create circuit breaker for a provider"""
        if provider_name not in self.circuit_breakers:
            cb_config = {**self.default_config}
            if config:
                cb_config.update(config)
            
            self.circuit_breakers[provider_name] = CircuitBreaker(**cb_config)
            # Created circuit breaker for provider
        
        return self.circuit_breakers[provider_name]
    
    async def execute_with_circuit_breaker(
        self,
        provider_name: str,
        operation: Callable,
        *args,
        **kwargs
    ):
        """Execute operation with circuit breaker protection"""
        circuit_breaker = self.get_circuit_breaker(provider_name)
        
        if not circuit_breaker.can_execute():
            error_msg = f"Circuit breaker is OPEN for provider {provider_name}"
            # Circuit breaker is OPEN
            raise Exception(error_msg)
        
        try:
            result = await operation(*args, **kwargs)
            circuit_breaker.record_success()
            return result
        except circuit_breaker.expected_exception as e:
            circuit_breaker.record_failure()
            # Circuit breaker recorded failure
            raise
        except Exception as e:
            # Don't record non-expected exceptions
            # Unexpected error in circuit breaker
            raise
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers"""
        return {
            provider: cb.get_state()
            for provider, cb in self.circuit_breakers.items()
        }
    
    def reset_circuit_breaker(self, provider_name: str):
        """Reset a specific circuit breaker"""
        if provider_name in self.circuit_breakers:
            self.circuit_breakers[provider_name].failure_count = 0
            self.circuit_breakers[provider_name].state = CircuitBreakerState.CLOSED
            self.circuit_breakers[provider_name].last_failure_time = None
            # Reset circuit breaker for provider

# Global circuit breaker middleware instance
circuit_breaker_middleware = CircuitBreakerMiddleware()


