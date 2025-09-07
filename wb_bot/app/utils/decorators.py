"""
Utility decorators for resilience patterns.

This module provides decorators for implementing common resilience patterns
like retry, rate limiting, and circuit breaker for robust API interactions.
"""

import asyncio
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
import random

from .logger import get_logger

logger = get_logger(__name__)


class RetryError(Exception):
    """Exception raised when retry attempts are exhausted."""
    pass


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    jitter: bool = True
):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Exponential backoff multiplier
        max_delay: Maximum delay between retries
        exceptions: Exception types to retry on
        jitter: Add random jitter to prevent thundering herd
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            error=str(e),
                            attempts=max_attempts
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    current_delay = min(delay * (backoff_factor ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        current_delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Function {func.__name__} failed, retrying in {current_delay:.2f}s",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        error=str(e),
                        delay=current_delay
                    )
                    
                    await asyncio.sleep(current_delay)
            
            raise RetryError(f"Function failed after {max_attempts} attempts") from last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            error=str(e),
                            attempts=max_attempts
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    current_delay = min(delay * (backoff_factor ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        current_delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Function {func.__name__} failed, retrying in {current_delay:.2f}s",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        error=str(e),
                        delay=current_delay
                    )
                    
                    time.sleep(current_delay)
            
            raise RetryError(f"Function failed after {max_attempts} attempts") from last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[float] = []
        self._lock = asyncio.Lock()
    
    async def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit."""
        async with self._lock:
            now = time.time()
            
            # Remove old requests outside the time window
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # Check if we can make a new request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    async def wait_until_allowed(self) -> None:
        """Wait until request is allowed."""
        while not await self.is_allowed():
            await asyncio.sleep(0.1)


# Global rate limiters storage
_rate_limiters: Dict[str, RateLimiter] = {}


def rate_limit(max_requests: int, time_window: float, key_func: Optional[Callable] = None):
    """
    Rate limiting decorator.
    
    Args:
        max_requests: Maximum number of requests allowed
        time_window: Time window in seconds
        key_func: Function to generate rate limit key from function args
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__module__}.{func.__name__}"
            
            # Get or create rate limiter
            if key not in _rate_limiters:
                _rate_limiters[key] = RateLimiter(max_requests, time_window)
            
            rate_limiter = _rate_limiters[key]
            
            # Check rate limit
            if not await rate_limiter.is_allowed():
                logger.warning(
                    f"Rate limit exceeded for {func.__name__}",
                    key=key,
                    max_requests=max_requests,
                    time_window=time_window
                )
                raise RateLimitError(f"Rate limit exceeded: {max_requests} requests per {time_window}s")
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Timeout in seconds before attempting to close circuit
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            # Check circuit state
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                    logger.info(f"Circuit breaker half-open for {func.__name__}")
                else:
                    raise CircuitBreakerError("Circuit breaker is open")
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Reset on success
                if self.state == "half-open":
                    self._reset()
                    logger.info(f"Circuit breaker closed for {func.__name__}")
                
                return result
                
            except self.expected_exception as e:
                self._record_failure()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.warning(
                        f"Circuit breaker opened for {func.__name__}",
                        failure_count=self.failure_count,
                        threshold=self.failure_threshold
                    )
                
                raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout)
    
    def _record_failure(self) -> None:
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
    
    def _reset(self) -> None:
        """Reset circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"


# Global circuit breakers storage
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def circuit_breaker(
    failure_threshold: int = 5,
    timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception,
    key_func: Optional[Callable] = None
):
    """
    Circuit breaker decorator.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        timeout: Timeout in seconds before attempting to close circuit
        expected_exception: Exception type that triggers circuit breaker
        key_func: Function to generate circuit breaker key from function args
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate circuit breaker key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__module__}.{func.__name__}"
            
            # Get or create circuit breaker
            if key not in _circuit_breakers:
                _circuit_breakers[key] = CircuitBreaker(
                    failure_threshold, timeout, expected_exception
                )
            
            circuit = _circuit_breakers[key]
            
            return await circuit.call(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


def timeout(seconds: float):
    """
    Timeout decorator for async functions.
    
    Args:
        seconds: Timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Function {func.__name__} timed out after {seconds}s"
                )
                raise
        
        return wrapper
    
    return decorator
