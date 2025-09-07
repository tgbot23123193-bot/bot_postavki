"""
Pydantic schemas for Wildberries API data validation.

This module contains all data models for WB API requests and responses
with proper validation and type safety.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SupplyType(str, Enum):
    """Supply type enumeration."""
    BOX = "box"
    MONO_PALLET = "mono_pallet"


class DeliveryType(str, Enum):
    """Delivery type enumeration."""
    DIRECT = "direct"
    TRANSIT = "transit"


class SlotStatus(str, Enum):
    """Slot status enumeration."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BOOKED = "booked"


class BookingStatus(str, Enum):
    """Booking status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


# Base schemas
class WBBaseModel(BaseModel):
    """Base model with common configuration."""
    
    class Config:
        use_enum_values = True
        validate_assignment = True
        extra = "forbid"


# Warehouse schemas
class WarehouseInfo(WBBaseModel):
    """Warehouse information."""
    
    id: int = Field(..., description="Warehouse ID")
    name: str = Field(..., description="Warehouse name")
    address: Optional[str] = Field(None, description="Warehouse address")
    is_active: bool = Field(True, description="Is warehouse active")


class WarehouseListResponse(WBBaseModel):
    """Response for warehouse list request."""
    
    warehouses: List[WarehouseInfo] = Field(..., description="List of warehouses")


# Slot schemas
class TimeSlot(WBBaseModel):
    """Time slot information."""
    
    time: str = Field(..., description="Time slot in format HH:MM-HH:MM")
    quota: int = Field(..., description="Available quota")
    coefficient: float = Field(..., description="Acceptance coefficient")
    
    @field_validator('coefficient')
    @classmethod
    def validate_coefficient(cls, v):
        """Validate coefficient is positive."""
        if v <= 0:
            raise ValueError("Coefficient must be positive")
        return v


class DaySlots(WBBaseModel):
    """Slots available for a specific day."""
    
    slot_date: date = Field(..., description="Date for slots")
    slots: List[TimeSlot] = Field(..., description="Available time slots")


class SlotsRequest(WBBaseModel):
    """Request for getting available slots."""
    
    warehouse_id: int = Field(..., description="Warehouse ID")
    date_from: date = Field(..., description="Start date")
    date_to: date = Field(..., description="End date")
    supply_type: SupplyType = Field(SupplyType.BOX, description="Supply type")
    delivery_type: DeliveryType = Field(DeliveryType.DIRECT, description="Delivery type")
    
    @field_validator('date_to')
    @classmethod
    def validate_date_range(cls, v, info):
        """Validate date range."""
        if info.data and 'date_from' in info.data and v < info.data['date_from']:
            raise ValueError("End date must be >= start date")
        return v


class SlotsResponse(WBBaseModel):
    """Response for slots request."""
    
    warehouse_id: int = Field(..., description="Warehouse ID")
    warehouse_name: str = Field(..., description="Warehouse name")
    supply_type: SupplyType = Field(..., description="Supply type")
    delivery_type: DeliveryType = Field(..., description="Delivery type")
    days: List[DaySlots] = Field(..., description="Available slots by day")


# Booking schemas
class BookingRequest(WBBaseModel):
    """Request for creating a booking."""
    
    warehouse_id: int = Field(..., description="Warehouse ID")
    booking_date: date = Field(..., description="Booking date")
    slot_time: str = Field(..., description="Time slot")
    supply_type: SupplyType = Field(SupplyType.BOX, description="Supply type")
    delivery_type: DeliveryType = Field(DeliveryType.DIRECT, description="Delivery type")


class BookingResponse(WBBaseModel):
    """Response for booking creation."""
    
    booking_id: str = Field(..., description="WB booking ID")
    warehouse_id: int = Field(..., description="Warehouse ID")
    booking_date: date = Field(..., description="Booking date")
    slot_time: str = Field(..., description="Time slot")
    coefficient: float = Field(..., description="Acceptance coefficient")
    status: BookingStatus = Field(..., description="Booking status")
    created_at: datetime = Field(..., description="Creation timestamp")


# Redistribution schemas
class RedistributionLimits(WBBaseModel):
    """Redistribution limits information."""
    
    daily_limit: int = Field(..., description="Daily redistribution limit")
    monthly_limit: int = Field(..., description="Monthly redistribution limit")
    used_today: int = Field(..., description="Used redistributions today")
    used_this_month: int = Field(..., description="Used redistributions this month")
    remaining_today: int = Field(..., description="Remaining redistributions today")
    remaining_this_month: int = Field(..., description="Remaining redistributions this month")


class RedistributionItem(WBBaseModel):
    """Item for redistribution."""
    
    sku: str = Field(..., description="SKU of the item")
    quantity: int = Field(..., description="Quantity to redistribute")
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v


class RedistributionRequest(WBBaseModel):
    """Request for creating redistribution."""
    
    from_warehouse_id: int = Field(..., description="Source warehouse ID")
    to_warehouse_id: int = Field(..., description="Target warehouse ID")
    items: List[RedistributionItem] = Field(..., description="Items to redistribute")
    
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v):
        """Validate items list is not empty."""
        if not v:
            raise ValueError("Items list cannot be empty")
        return v


class RedistributionResponse(WBBaseModel):
    """Response for redistribution creation."""
    
    request_id: str = Field(..., description="Redistribution request ID")
    from_warehouse_id: int = Field(..., description="Source warehouse ID")
    to_warehouse_id: int = Field(..., description="Target warehouse ID")
    items_count: int = Field(..., description="Number of items")
    status: str = Field(..., description="Request status")
    created_at: datetime = Field(..., description="Creation timestamp")


# Error schemas
class WBErrorDetail(WBBaseModel):
    """WB API error detail."""
    
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field causing error")


class WBErrorResponse(WBBaseModel):
    """WB API error response."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[List[WBErrorDetail]] = Field(None, description="Error details")
    timestamp: datetime = Field(..., description="Error timestamp")


# API key validation schemas
class APIKeyValidationRequest(WBBaseModel):
    """Request for API key validation."""
    
    api_key: str = Field(..., description="API key to validate")


class APIKeyValidationResponse(WBBaseModel):
    """Response for API key validation."""
    
    is_valid: bool = Field(..., description="Is API key valid")
    permissions: Optional[List[str]] = Field(None, description="API key permissions")
    rate_limit: Optional[Dict[str, int]] = Field(None, description="Rate limit info")
    expires_at: Optional[datetime] = Field(None, description="API key expiration")


# Generic response schemas
class PaginatedResponse(WBBaseModel):
    """Paginated response wrapper."""
    
    items: List[Any] = Field(..., description="Response items")
    total: int = Field(..., description="Total items count")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")


class HealthCheckResponse(WBBaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    response_time: float = Field(..., description="Response time in seconds")
