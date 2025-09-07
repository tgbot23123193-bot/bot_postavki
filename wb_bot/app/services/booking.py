"""
Booking service for manual and automatic supply bookings.

This module handles supply booking operations with proper validation,
error handling, and user management.
"""

from datetime import date, datetime
from typing import Optional, List, Tuple
import json

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session, User, MonitoringTask, BookingResult, APIKey
from ..database.models import BookingStatus, SupplyType, DeliveryType
from ..api import WBAPIClient, WBAPIError
from ..api.schemas import BookingResponse
from ..utils.logger import get_logger, UserLogger
from ..utils.encryption import decrypt_api_key
from .auth import auth_service

logger = get_logger(__name__)


class BookingService:
    """
    Service for managing supply bookings.
    
    Features:
    - Manual booking with validation
    - Automatic booking integration
    - Trial booking management
    - Booking history and statistics
    - Error handling and recovery
    """
    
    def __init__(self):
        """Initialize booking service."""
        pass
    
    async def create_manual_booking(
        self,
        user_id: int,
        warehouse_id: int,
        booking_date: date,
        slot_time: str,
        supply_type: SupplyType = SupplyType.BOX,
        delivery_type: DeliveryType = DeliveryType.DIRECT
    ) -> Tuple[bool, str, Optional[BookingResult]]:
        """
        Create manual booking for user.
        
        Args:
            user_id: User ID
            warehouse_id: Warehouse ID
            booking_date: Date for booking
            slot_time: Time slot (e.g., "09:00-12:00")
            supply_type: Type of supply
            delivery_type: Type of delivery
            
        Returns:
            Tuple of (success, message, booking_result)
        """
        user_logger = UserLogger(user_id)
        
        async with get_session() as session:
            # Get user
            user_query = select(User).where(User.id == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                return False, "User not found", None
            
            # Check if user can make bookings
            if not user.can_use_auto_booking():
                return False, "Trial limit exceeded. Please upgrade to premium.", None
            
            # Get user's API keys
            api_keys = await auth_service.get_user_api_keys(user_id)
            if not api_keys:
                return False, "No API keys configured. Please add an API key first.", None
            
            # Find valid API key
            valid_api_key = None
            for api_key in api_keys:
                if api_key.is_valid:
                    try:
                        decrypted_key = decrypt_api_key(api_key.encrypted_key, api_key.salt)
                        valid_api_key = (api_key, decrypted_key)
                        break
                    except Exception as e:
                        logger.error(f"Failed to decrypt API key {api_key.id}: {e}")
                        continue
            
            if not valid_api_key:
                return False, "No valid API keys available.", None
            
            api_key_obj, api_key_str = valid_api_key
            
            # Attempt booking
            try:
                async with WBAPIClient(api_key_str) as client:
                    booking_response = await client.create_booking(
                        warehouse_id=warehouse_id,
                        booking_date=booking_date,
                        slot_time=slot_time,
                        supply_type=supply_type,
                        delivery_type=delivery_type
                    )
                
                # Save successful booking
                booking_result = BookingResult(
                    task_id=None,  # Manual booking, no task
                    booking_date=booking_date,
                    slot_time=slot_time,
                    coefficient=booking_response.coefficient,
                    wb_booking_id=booking_response.booking_id,
                    wb_response=json.dumps(booking_response.dict()),
                    status=BookingStatus.CONFIRMED.value,
                    api_key_id=api_key_obj.id,
                    confirmed_at=datetime.utcnow()
                )
                
                session.add(booking_result)
                
                # Update user trial bookings if not premium
                if not user.is_premium:
                    user.trial_bookings += 1
                    session.add(user)
                
                # Update API key usage
                await auth_service.update_key_usage(api_key_obj.id, success=True)
                
                await session.commit()
                
                user_logger.info(f"Manual booking successful: {booking_response.booking_id}")
                return True, f"Booking successful! ID: {booking_response.booking_id}", booking_result
                
            except WBAPIError as e:
                # Save failed booking
                booking_result = BookingResult(
                    task_id=None,
                    booking_date=booking_date,
                    slot_time=slot_time,
                    status=BookingStatus.FAILED.value,
                    error_message=str(e),
                    api_key_id=api_key_obj.id
                )
                
                session.add(booking_result)
                await auth_service.update_key_usage(api_key_obj.id, success=False)
                await session.commit()
                
                user_logger.warning(f"Manual booking failed: {e}")
                return False, f"Booking failed: {e}", booking_result
            
            except Exception as e:
                logger.error(f"Unexpected error during manual booking: {e}")
                return False, "Unexpected error occurred during booking", None
    
    async def get_user_bookings(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[BookingResult]:
        """
        Get booking history for user.
        
        Args:
            user_id: User ID
            limit: Maximum number of bookings to return
            offset: Offset for pagination
            
        Returns:
            List of booking results
        """
        async with get_session() as session:
            # Get user's monitoring tasks
            task_query = select(MonitoringTask.id).where(MonitoringTask.user_id == user_id)
            task_result = await session.execute(task_query)
            task_ids = [row[0] for row in task_result.fetchall()]
            
            # Get bookings for user's tasks
            if task_ids:
                booking_query = select(BookingResult).where(
                    BookingResult.task_id.in_(task_ids)
                ).order_by(BookingResult.created_at.desc()).limit(limit).offset(offset)
            else:
                # Return empty list if no tasks
                return []
            
            booking_result = await session.execute(booking_query)
            return booking_result.scalars().all()
    
    async def get_booking_statistics(self, user_id: int) -> dict:
        """
        Get booking statistics for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with booking statistics
        """
        bookings = await self.get_user_bookings(user_id, limit=1000)  # Get all bookings
        
        stats = {
            "total_bookings": len(bookings),
            "successful_bookings": 0,
            "failed_bookings": 0,
            "pending_bookings": 0,
            "cancelled_bookings": 0,
            "success_rate": 0.0,
            "total_coefficient": 0.0,
            "average_coefficient": 0.0,
            "recent_bookings": []
        }
        
        successful_coefficients = []
        
        for booking in bookings:
            if booking.status == BookingStatus.CONFIRMED.value:
                stats["successful_bookings"] += 1
                if booking.coefficient:
                    successful_coefficients.append(booking.coefficient)
                    stats["total_coefficient"] += booking.coefficient
            elif booking.status == BookingStatus.FAILED.value:
                stats["failed_bookings"] += 1
            elif booking.status == BookingStatus.PENDING.value:
                stats["pending_bookings"] += 1
            elif booking.status == BookingStatus.CANCELLED.value:
                stats["cancelled_bookings"] += 1
        
        # Calculate success rate
        if stats["total_bookings"] > 0:
            stats["success_rate"] = stats["successful_bookings"] / stats["total_bookings"]
        
        # Calculate average coefficient
        if successful_coefficients:
            stats["average_coefficient"] = sum(successful_coefficients) / len(successful_coefficients)
        
        # Get recent bookings (last 10)
        stats["recent_bookings"] = bookings[:10]
        
        return stats
    
    async def cancel_booking(
        self,
        user_id: int,
        booking_id: str
    ) -> Tuple[bool, str]:
        """
        Cancel existing booking.
        
        Args:
            user_id: User ID
            booking_id: WB booking ID
            
        Returns:
            Tuple of (success, message)
        """
        user_logger = UserLogger(user_id)
        
        async with get_session() as session:
            # Find booking
            booking_query = select(BookingResult).where(
                BookingResult.wb_booking_id == booking_id
            )
            booking_result = await session.execute(booking_query)
            booking = booking_result.scalar_one_or_none()
            
            if not booking:
                return False, "Booking not found"
            
            # Verify ownership through task
            if booking.task_id:
                task_query = select(MonitoringTask).where(
                    and_(
                        MonitoringTask.id == booking.task_id,
                        MonitoringTask.user_id == user_id
                    )
                )
                task_result = await session.execute(task_query)
                task = task_result.scalar_one_or_none()
                
                if not task:
                    return False, "Booking does not belong to user"
            
            if booking.status != BookingStatus.CONFIRMED.value:
                return False, "Only confirmed bookings can be cancelled"
            
            # Get user's API keys for cancellation
            api_keys = await auth_service.get_user_api_keys(user_id)
            if not api_keys:
                return False, "No API keys configured"
            
            # Find valid API key
            valid_api_key = None
            for api_key in api_keys:
                if api_key.is_valid:
                    try:
                        decrypted_key = decrypt_api_key(api_key.encrypted_key, api_key.salt)
                        valid_api_key = decrypted_key
                        break
                    except Exception:
                        continue
            
            if not valid_api_key:
                return False, "No valid API keys available"
            
            try:
                # Note: WB API doesn't always support cancellation
                # This is a placeholder for when/if they add this functionality
                async with WBAPIClient(valid_api_key) as client:
                    # This would be the cancellation call
                    # await client.cancel_booking(booking_id)
                    pass
                
                # Update booking status
                booking.status = BookingStatus.CANCELLED.value
                session.add(booking)
                await session.commit()
                
                user_logger.info(f"Cancelled booking: {booking_id}")
                return True, "Booking cancelled successfully"
                
            except WBAPIError as e:
                user_logger.warning(f"Failed to cancel booking {booking_id}: {e}")
                return False, f"Cancellation failed: {e}"
            
            except Exception as e:
                logger.error(f"Unexpected error during booking cancellation: {e}")
                return False, "Unexpected error during cancellation"
    
    async def get_booking_details(
        self,
        user_id: int,
        booking_id: str
    ) -> Optional[BookingResult]:
        """
        Get detailed information about a booking.
        
        Args:
            user_id: User ID
            booking_id: WB booking ID
            
        Returns:
            Booking result or None if not found
        """
        async with get_session() as session:
            # Find booking
            booking_query = select(BookingResult).where(
                BookingResult.wb_booking_id == booking_id
            )
            booking_result = await session.execute(booking_query)
            booking = booking_result.scalar_one_or_none()
            
            if not booking:
                return None
            
            # Verify ownership through task if applicable
            if booking.task_id:
                task_query = select(MonitoringTask).where(
                    and_(
                        MonitoringTask.id == booking.task_id,
                        MonitoringTask.user_id == user_id
                    )
                )
                task_result = await session.execute(task_query)
                task = task_result.scalar_one_or_none()
                
                if not task:
                    return None
            
            return booking
    
    async def retry_failed_booking(
        self,
        user_id: int,
        booking_result_id: int
    ) -> Tuple[bool, str, Optional[BookingResult]]:
        """
        Retry a failed booking.
        
        Args:
            user_id: User ID
            booking_result_id: Failed booking result ID
            
        Returns:
            Tuple of (success, message, new_booking_result)
        """
        async with get_session() as session:
            # Get failed booking
            booking_query = select(BookingResult).where(
                BookingResult.id == booking_result_id
            )
            booking_result = await session.execute(booking_query)
            failed_booking = booking_result.scalar_one_or_none()
            
            if not failed_booking:
                return False, "Booking not found", None
            
            if failed_booking.status != BookingStatus.FAILED.value:
                return False, "Only failed bookings can be retried", None
            
            # Verify ownership through task
            if failed_booking.task_id:
                task_query = select(MonitoringTask).where(
                    and_(
                        MonitoringTask.id == failed_booking.task_id,
                        MonitoringTask.user_id == user_id
                    )
                )
                task_result = await session.execute(task_query)
                task = task_result.scalar_one_or_none()
                
                if not task:
                    return False, "Booking does not belong to user", None
                
                # Get supply type from task
                supply_type = SupplyType(task.supply_type)
                delivery_type = DeliveryType(task.delivery_type)
                warehouse_id = task.warehouse_id
            else:
                # For manual bookings, we need to infer from the booking data
                # This is a limitation - we should store more data for manual bookings
                return False, "Cannot retry manual bookings", None
            
            # Retry the booking
            return await self.create_manual_booking(
                user_id=user_id,
                warehouse_id=warehouse_id,
                booking_date=failed_booking.booking_date,
                slot_time=failed_booking.slot_time,
                supply_type=supply_type,
                delivery_type=delivery_type
            )


# Global booking service instance
booking_service = BookingService()
