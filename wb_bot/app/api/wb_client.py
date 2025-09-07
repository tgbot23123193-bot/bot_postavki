"""
Professional Wildberries API client with enterprise features.

This module provides a robust HTTP client for interacting with WB API
with connection pooling, retry logic, circuit breaker, and comprehensive
error handling.
"""

import asyncio
import json
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, ClientError, ClientResponseError, ClientTimeout

from ..config import get_settings
from ..utils.decorators import retry, circuit_breaker, timeout
from ..utils.logger import get_logger, log_api_request
from .schemas import (
    SupplyType, DeliveryType, SlotsRequest, SlotsResponse, 
    BookingRequest, BookingResponse, RedistributionRequest, 
    RedistributionResponse, RedistributionLimits, WarehouseListResponse,
    WBErrorResponse, APIKeyValidationResponse, HealthCheckResponse
)

logger = get_logger(__name__)


class WBAPIError(Exception):
    """Base exception for WB API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class WBAuthenticationError(WBAPIError):
    """Authentication error (401)."""
    pass


class WBRateLimitError(WBAPIError):
    """Rate limit error (429)."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class WBValidationError(WBAPIError):
    """Validation error (400)."""
    pass


class WBNotFoundError(WBAPIError):
    """Resource not found error (404)."""
    pass


class WBServerError(WBAPIError):
    """Server error (5xx)."""
    pass


class WBAPIClient:
    """
    Professional Wildberries API client.
    
    Features:
    - Connection pooling with aiohttp ClientSession
    - Automatic retry with exponential backoff
    - Circuit breaker for protecting against cascading failures
    - Rate limiting protection
    - Comprehensive error handling and logging
    - Request/response validation with Pydantic
    - Health checks and monitoring
    """
    
    def __init__(self, api_key: str, session: Optional[ClientSession] = None):
        """
        Initialize WB API client.
        
        Args:
            api_key: Wildberries API key
            session: Optional aiohttp session (will create new if None)
        """
        self.api_key = api_key
        self.settings = get_settings()
        self.base_url = self.settings.wildberries.base_url
        
        # Session will be created in __aenter__
        self._session: Optional[ClientSession] = session
        self._owned_session = session is None
        
        # Request configuration
        self.timeout = ClientTimeout(total=self.settings.wildberries.timeout)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"WB-Auto-Bot/{self.settings.version}",
        }
        
        # Rate limiting and circuit breaker state
        self._last_request_time = 0.0
        self._request_count = 0
        self._rate_limit_reset_time = 0.0
    
    async def __aenter__(self) -> "WBAPIClient":
        """Async context manager entry."""
        if self._session is None:
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=30,  # Connections per host
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            
            self._session = ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=self.headers,
                raise_for_status=False,  # We'll handle status codes manually
            )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._owned_session and self._session:
            await self._session.close()
            self._session = None
    
    def _get_session(self) -> ClientSession:
        """Get session with validation."""
        if self._session is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._session
    
    async def _handle_rate_limit(self, response: aiohttp.ClientResponse) -> None:
        """Handle rate limiting from response headers."""
        if response.status == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    delay = int(retry_after)
                    logger.warning(f"Rate limited, waiting {delay} seconds")
                    raise WBRateLimitError(
                        f"Rate limit exceeded, retry after {delay} seconds",
                        retry_after=delay,
                        status_code=429
                    )
                except ValueError:
                    pass
            
            # Default rate limit delay
            delay = self.settings.wildberries.rate_limit_delay
            logger.warning(f"Rate limited, waiting {delay} seconds")
            raise WBRateLimitError(
                f"Rate limit exceeded, retry after {delay} seconds",
                retry_after=delay,
                status_code=429
            )
    
    async def _handle_error_response(self, response: aiohttp.ClientResponse) -> None:
        """Handle HTTP error responses."""
        try:
            error_data = await response.json()
        except Exception:
            error_data = {"error": "Unknown error", "message": await response.text()}
        
        if response.status == 401:
            raise WBAuthenticationError(
                "Authentication failed. Check your API key.",
                status_code=401,
                response_data=error_data
            )
        elif response.status == 400:
            raise WBValidationError(
                error_data.get("message", "Validation error"),
                status_code=400,
                response_data=error_data
            )
        elif response.status == 404:
            raise WBNotFoundError(
                error_data.get("message", "Resource not found"),
                status_code=404,
                response_data=error_data
            )
        elif response.status == 429:
            await self._handle_rate_limit(response)
        elif response.status >= 500:
            raise WBServerError(
                error_data.get("message", "Server error"),
                status_code=response.status,
                response_data=error_data
            )
        else:
            raise WBAPIError(
                error_data.get("message", f"HTTP {response.status}"),
                status_code=response.status,
                response_data=error_data
            )
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff_factor=2.0,
        exceptions=(WBServerError, WBRateLimitError, ClientError)
    )
    @circuit_breaker(
        failure_threshold=5,
        timeout=300.0,
        expected_exception=WBServerError
    )
    @timeout(30.0)
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling and logging.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body data
            params: URL parameters
            
        Returns:
            Response data as dictionary
        """
        session = self._get_session()
        url = urljoin(self.base_url, endpoint)
        
        start_time = time.time()
        
        try:
            # Prepare request
            kwargs = {"params": params} if params else {}
            if data:
                kwargs["data"] = json.dumps(data)
            
            # Make request
            async with session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                
                # Log request
                log_api_request(
                    method=method,
                    url=url,
                    status_code=response.status,
                    response_time=response_time,
                    api_key_last4=self.api_key[-4:] if len(self.api_key) > 4 else "****"
                )
                
                # Handle errors
                if response.status >= 400:
                    await self._handle_error_response(response)
                
                # Parse response
                try:
                    result = await response.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    result = {"raw_response": await response.text()}
                
                return result
        
        except Exception as e:
            response_time = time.time() - start_time
            log_api_request(
                method=method,
                url=url,
                response_time=response_time,
                error=str(e),
                api_key_last4=self.api_key[-4:] if len(self.api_key) > 4 else "****"
            )
            raise
    
    async def validate_api_key(self) -> APIKeyValidationResponse:
        """
        Validate API key by making a test request.
        
        Returns:
            API key validation response
        """
        try:
            # Try to get warehouses list as validation
            response = await self._make_request("GET", "/api/v3/warehouses")
            
            return APIKeyValidationResponse(
                is_valid=True,
                permissions=["warehouses:read"],  # This could be expanded
                rate_limit=None,  # WB doesn't always provide this
                expires_at=None   # WB doesn't provide expiration info
            )
        except WBAuthenticationError:
            return APIKeyValidationResponse(
                is_valid=False,
                permissions=[],
                rate_limit=None,
                expires_at=None
            )
    
    async def get_warehouses(self) -> WarehouseListResponse:
        """
        Get list of available warehouses.
        
        Returns:
            List of warehouses
        """
        response = await self._make_request("GET", "/api/v3/warehouses")
        return WarehouseListResponse.parse_obj(response)
    
    async def get_available_slots(
        self,
        warehouse_id: int,
        date_from: date,
        date_to: date,
        supply_type: SupplyType = SupplyType.BOX,
        delivery_type: DeliveryType = DeliveryType.DIRECT
    ) -> SlotsResponse:
        """
        Get available time slots for warehouse.
        
        Args:
            warehouse_id: Warehouse ID
            date_from: Start date
            date_to: End date
            supply_type: Type of supply
            delivery_type: Type of delivery
            
        Returns:
            Available slots response
        """
        request_data = SlotsRequest(
            warehouse_id=warehouse_id,
            date_from=date_from,
            date_to=date_to,
            supply_type=supply_type,
            delivery_type=delivery_type
        )
        
        # Choose endpoint based on supply type
        if supply_type == SupplyType.BOX:
            endpoint = "/api/v3/supplies/slots/box"
        else:
            endpoint = "/api/v3/supplies/slots/mono-pallet"
        
        params = {
            "warehouseId": warehouse_id,
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "deliveryType": delivery_type.value
        }
        
        response = await self._make_request("GET", endpoint, params=params)
        return SlotsResponse.parse_obj(response)
    
    async def create_booking(
        self,
        warehouse_id: int,
        booking_date: date,
        slot_time: str,
        supply_type: SupplyType = SupplyType.BOX,
        delivery_type: DeliveryType = DeliveryType.DIRECT
    ) -> BookingResponse:
        """
        Create supply booking.
        
        Args:
            warehouse_id: Warehouse ID
            booking_date: Date for booking
            slot_time: Time slot
            supply_type: Type of supply
            delivery_type: Type of delivery
            
        Returns:
            Booking response
        """
        request_data = BookingRequest(
            warehouse_id=warehouse_id,
            booking_date=booking_date,
            slot_time=slot_time,
            supply_type=supply_type,
            delivery_type=delivery_type
        )
        
        # Choose endpoint based on supply type
        if supply_type == SupplyType.BOX:
            endpoint = "/api/v3/supplies/booking/box"
        else:
            endpoint = "/api/v3/supplies/booking/mono-pallet"
        
        response = await self._make_request("POST", endpoint, data=request_data.dict())
        return BookingResponse.parse_obj(response)
    
    async def get_redistribution_limits(self) -> RedistributionLimits:
        """
        Get redistribution limits for current API key.
        
        Returns:
            Redistribution limits
        """
        response = await self._make_request("GET", "/api/v3/redistribution/limits")
        return RedistributionLimits.parse_obj(response)
    
    async def create_redistribution_request(
        self,
        from_warehouse_id: int,
        to_warehouse_id: int,
        items: List[Dict[str, Any]]
    ) -> RedistributionResponse:
        """
        Create redistribution request.
        
        Args:
            from_warehouse_id: Source warehouse ID
            to_warehouse_id: Target warehouse ID
            items: List of items to redistribute
            
        Returns:
            Redistribution response
        """
        request_data = RedistributionRequest(
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            items=items
        )
        
        response = await self._make_request(
            "POST", 
            "/api/v3/redistribution/requests", 
            data=request_data.dict()
        )
        return RedistributionResponse.parse_obj(response)
    
    async def health_check(self) -> HealthCheckResponse:
        """
        Perform health check.
        
        Returns:
            Health check response
        """
        start_time = time.time()
        
        try:
            await self._make_request("GET", "/api/v3/health")
            response_time = time.time() - start_time
            
            return HealthCheckResponse(
                status="healthy",
                timestamp=datetime.utcnow(),
                response_time=response_time
            )
        except Exception as e:
            response_time = time.time() - start_time
            
            return HealthCheckResponse(
                status="unhealthy",
                timestamp=datetime.utcnow(),
                response_time=response_time
            )


# Factory function for creating API clients
def create_wb_client(api_key: str) -> WBAPIClient:
    """
    Factory function to create WB API client.
    
    Args:
        api_key: Wildberries API key
        
    Returns:
        Configured WB API client
    """
    return WBAPIClient(api_key)
