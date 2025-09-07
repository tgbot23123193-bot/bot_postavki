"""
SQLAlchemy database models for WB Auto-Booking Bot.

This module contains all database models with proper relationships,
indexes, and constraints for optimal performance and data integrity.
"""

from datetime import datetime, date
from typing import List, Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Date, Integer, String, 
    ForeignKey, Float, Text, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


Base = declarative_base()


class SupplyType(PyEnum):
    """Supply type enumeration."""
    BOX = "box"  # короб
    MONO_PALLET = "mono_pallet"  # монопаллета


class DeliveryType(PyEnum):
    """Delivery type enumeration."""
    DIRECT = "direct"  # прямая
    TRANSIT = "transit"  # транзитная


class BookingStatus(PyEnum):
    """Booking status enumeration."""
    PENDING = "pending"  # ожидает
    CONFIRMED = "confirmed"  # подтверждено
    CANCELLED = "cancelled"  # отменено
    FAILED = "failed"  # ошибка


class MonitoringMode(PyEnum):
    """Monitoring mode enumeration."""
    NOTIFICATION = "notification"  # только уведомления
    AUTO_BOOKING = "auto_booking"  # автобронирование


class User(Base):
    """User model for storing Telegram user information."""
    
    __tablename__ = 'users'
    __allow_unmapped__ = True
    
    # Primary key - Telegram user ID
    id: int = Column(BigInteger, primary_key=True, index=True)
    
    # User info
    username: Optional[str] = Column(String(255), nullable=True, index=True)
    first_name: Optional[str] = Column(String(255), nullable=True)
    last_name: Optional[str] = Column(String(255), nullable=True)
    language_code: Optional[str] = Column(String(10), nullable=True, default='ru')
    
    # Status and settings
    is_active: bool = Column(Boolean, default=True, nullable=False, index=True)
    is_premium: bool = Column(Boolean, default=False, nullable=False)
    trial_bookings: int = Column(Integer, default=0, nullable=False)
    
    # User preferences for monitoring
    default_check_interval: int = Column(Integer, default=30, nullable=False)
    default_max_coefficient: float = Column(Float, default=2.0, nullable=False)
    default_supply_type: str = Column(String(20), default=SupplyType.BOX.value, nullable=False)
    default_delivery_type: str = Column(String(20), default=DeliveryType.DIRECT.value, nullable=False)
    default_monitoring_mode: str = Column(String(20), default=MonitoringMode.NOTIFICATION.value, nullable=False)
    
    # Timestamps
    created_at: datetime = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_activity: datetime = Column(DateTime, nullable=True, index=True)
    
    # Relationships
    api_keys: List["APIKey"] = relationship(
        "APIKey", 
        back_populates="user", 
        cascade="all, delete-orphan",
        order_by="APIKey.created_at.desc()"
    )
    monitoring_tasks: List["MonitoringTask"] = relationship(
        "MonitoringTask", 
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="MonitoringTask.created_at.desc()"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint('trial_bookings >= 0', name='check_trial_bookings_positive'),
        CheckConstraint('default_check_interval >= 1', name='check_interval_positive'),
        CheckConstraint('default_max_coefficient >= 1.0', name='check_coefficient_positive'),
        Index('idx_user_activity', 'is_active', 'last_activity'),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
    
    def is_trial_available(self) -> bool:
        """Check if user has trial bookings available."""
        return self.trial_bookings < 2  # As per requirements
    
    def can_use_auto_booking(self) -> bool:
        """Check if user can use auto-booking feature."""
        return self.is_premium or self.is_trial_available()


class APIKey(Base):
    """API key model for storing encrypted Wildberries API keys."""
    
    __tablename__ = 'api_keys'
    __allow_unmapped__ = True
    
    # Primary key
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to user
    user_id: int = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Encrypted API key data
    encrypted_key: str = Column(String(500), nullable=False)
    salt: str = Column(String(100), nullable=False)  # Unique salt for each key
    
    # Key metadata
    name: Optional[str] = Column(String(100), nullable=True)  # User-friendly name
    description: Optional[str] = Column(Text, nullable=True)
    
    # Status and validation
    is_valid: bool = Column(Boolean, default=True, nullable=False, index=True)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    last_validation: Optional[datetime] = Column(DateTime, nullable=True)
    validation_error: Optional[str] = Column(Text, nullable=True)
    
    # Usage statistics
    last_used: Optional[datetime] = Column(DateTime, nullable=True, index=True)
    total_requests: int = Column(Integer, default=0, nullable=False)
    successful_requests: int = Column(Integer, default=0, nullable=False)
    failed_requests: int = Column(Integer, default=0, nullable=False)
    
    # Rate limiting
    requests_per_minute: int = Column(Integer, default=0, nullable=False)
    last_rate_reset: datetime = Column(DateTime, default=func.now(), nullable=False)
    
    # Timestamps
    created_at: datetime = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user: "User" = relationship("User", back_populates="api_keys")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('total_requests >= 0', name='check_total_requests_positive'),
        CheckConstraint('successful_requests >= 0', name='check_successful_requests_positive'),
        CheckConstraint('failed_requests >= 0', name='check_failed_requests_positive'),
        CheckConstraint('requests_per_minute >= 0', name='check_rpm_positive'),
        Index('idx_apikey_user_active', 'user_id', 'is_active'),
        Index('idx_apikey_usage', 'last_used', 'total_requests'),
    )
    
    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, user_id={self.user_id}, name={self.name})>"
    
    def get_success_rate(self) -> float:
        """Calculate success rate of API key usage."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    def is_rate_limited(self, limit: int = 60) -> bool:
        """Check if API key is rate limited."""
        return self.requests_per_minute >= limit


class MonitoringTask(Base):
    """Monitoring task model for tracking warehouse slot monitoring."""
    
    __tablename__ = 'monitoring_tasks'
    __allow_unmapped__ = True
    
    # Primary key
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to user
    user_id: int = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Warehouse information
    warehouse_id: int = Column(Integer, nullable=False, index=True)
    warehouse_name: str = Column(String(100), nullable=False)
    
    # Date range for monitoring
    date_from: date = Column(Date, nullable=False, index=True)
    date_to: date = Column(Date, nullable=False, index=True)
    
    # Monitoring settings
    check_interval: int = Column(Integer, default=30, nullable=False)  # seconds
    max_coefficient: float = Column(Float, default=2.0, nullable=False)
    supply_type: str = Column(String(20), default=SupplyType.BOX.value, nullable=False)
    delivery_type: str = Column(String(20), default=DeliveryType.DIRECT.value, nullable=False)
    monitoring_mode: str = Column(String(20), default=MonitoringMode.NOTIFICATION.value, nullable=False)
    
    # Status and control
    is_active: bool = Column(Boolean, default=True, nullable=False, index=True)
    is_paused: bool = Column(Boolean, default=False, nullable=False)
    
    # Statistics
    total_checks: int = Column(Integer, default=0, nullable=False)
    slots_found: int = Column(Integer, default=0, nullable=False)
    successful_bookings: int = Column(Integer, default=0, nullable=False)
    failed_bookings: int = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at: datetime = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_check: Optional[datetime] = Column(DateTime, nullable=True, index=True)
    next_check: Optional[datetime] = Column(DateTime, nullable=True, index=True)
    
    # Relationships
    user: "User" = relationship("User", back_populates="monitoring_tasks")
    bookings: List["BookingResult"] = relationship(
        "BookingResult", 
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="BookingResult.created_at.desc()"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint('date_to >= date_from', name='check_date_range_valid'),
        CheckConstraint('check_interval >= 1', name='check_interval_positive'),
        CheckConstraint('max_coefficient >= 1.0', name='check_coefficient_positive'),
        CheckConstraint('total_checks >= 0', name='check_total_checks_positive'),
        CheckConstraint('slots_found >= 0', name='check_slots_found_positive'),
        CheckConstraint('successful_bookings >= 0', name='check_successful_bookings_positive'),
        CheckConstraint('failed_bookings >= 0', name='check_failed_bookings_positive'),
        Index('idx_monitoring_active', 'is_active', 'next_check'),
        Index('idx_monitoring_warehouse', 'warehouse_id', 'date_from', 'date_to'),
        UniqueConstraint('user_id', 'warehouse_id', 'date_from', 'date_to', 'supply_type', 'delivery_type', 
                        name='uq_monitoring_task'),
    )
    
    def __repr__(self) -> str:
        return f"<MonitoringTask(id={self.id}, warehouse={self.warehouse_name}, user_id={self.user_id})>"
    
    def is_expired(self) -> bool:
        """Check if monitoring task is expired."""
        return date.today() > self.date_to
    
    def get_success_rate(self) -> float:
        """Calculate booking success rate."""
        total_attempts = self.successful_bookings + self.failed_bookings
        if total_attempts == 0:
            return 0.0
        return self.successful_bookings / total_attempts


class BookingResult(Base):
    """Booking result model for storing booking attempts and results."""
    
    __tablename__ = 'booking_results'
    __allow_unmapped__ = True
    
    # Primary key
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to monitoring task
    task_id: int = Column(Integer, ForeignKey('monitoring_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Booking details
    booking_date: date = Column(Date, nullable=False, index=True)
    slot_time: Optional[str] = Column(String(50), nullable=True)  # e.g., "09:00-12:00"
    coefficient: Optional[float] = Column(Float, nullable=True)
    
    # WB API response
    wb_booking_id: Optional[str] = Column(String(100), nullable=True, index=True)
    wb_response: Optional[str] = Column(Text, nullable=True)  # JSON response from WB
    
    # Status and error handling
    status: str = Column(String(50), default=BookingStatus.PENDING.value, nullable=False, index=True)
    error_message: Optional[str] = Column(Text, nullable=True)
    retry_count: int = Column(Integer, default=0, nullable=False)
    
    # API key used for booking
    api_key_id: Optional[int] = Column(Integer, ForeignKey('api_keys.id'), nullable=True)
    
    # Timestamps
    created_at: datetime = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    confirmed_at: Optional[datetime] = Column(DateTime, nullable=True)
    
    # Relationships
    task: "MonitoringTask" = relationship("MonitoringTask", back_populates="bookings")
    api_key: Optional["APIKey"] = relationship("APIKey")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
        CheckConstraint('coefficient >= 1.0 OR coefficient IS NULL', name='check_coefficient_valid'),
        Index('idx_booking_status', 'status', 'created_at'),
        Index('idx_booking_date', 'booking_date', 'status'),
        Index('idx_booking_wb_id', 'wb_booking_id'),
    )
    
    def __repr__(self) -> str:
        return f"<BookingResult(id={self.id}, task_id={self.task_id}, status={self.status})>"
    
    def is_successful(self) -> bool:
        """Check if booking was successful."""
        return self.status == BookingStatus.CONFIRMED.value
    
    def is_pending(self) -> bool:
        """Check if booking is still pending."""
        return self.status == BookingStatus.PENDING.value


# Create indexes for optimal query performance
def create_additional_indexes():
    """Create additional indexes for better performance."""
    
    # Composite indexes for common queries
    user_active_tasks = Index(
        'idx_user_active_monitoring', 
        MonitoringTask.user_id, 
        MonitoringTask.is_active, 
        MonitoringTask.next_check
    )
    
    booking_task_status = Index(
        'idx_booking_task_status',
        BookingResult.task_id,
        BookingResult.status,
        BookingResult.created_at
    )
    
    apikey_user_valid = Index(
        'idx_apikey_user_valid',
        APIKey.user_id,
        APIKey.is_valid,
        APIKey.is_active
    )
    
    return [user_active_tasks, booking_task_status, apikey_user_valid]
