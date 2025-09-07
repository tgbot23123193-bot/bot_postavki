"""
High-performance slot monitoring service.

This module provides enterprise-grade monitoring of WB warehouse slots
with concurrent processing, intelligent caching, and automatic booking.
"""

import asyncio
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Set, Optional, Tuple, Any
import json

try:
    import redis.asyncio as aioredis
except ImportError:
    import aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session, MonitoringTask, User, APIKey, BookingResult
from ..database.models import MonitoringMode, BookingStatus, SupplyType, DeliveryType
from ..api import WBAPIClient, WBAPIError
from ..api.schemas import SlotsResponse, TimeSlot
from ..utils.logger import get_logger, TaskLogger
from ..utils.decorators import retry
from ..utils.encryption import decrypt_api_key

logger = get_logger(__name__)


class SlotMonitoringService:
    """
    High-performance slot monitoring service.
    
    Features:
    - Concurrent monitoring of 1000+ tasks
    - Redis caching with configurable TTL
    - Intelligent API key rotation
    - Automatic booking for qualifying slots
    - Comprehensive error handling and recovery
    - Performance metrics and monitoring
    """
    
    def __init__(self):
        """Initialize monitoring service."""
        self.settings = get_settings()
        self.redis: Optional[aioredis.Redis] = None
        self.is_running = False
        self.active_tasks: Dict[int, asyncio.Task] = {}
        
        # Performance metrics
        self.metrics = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "slots_found": 0,
            "bookings_attempted": 0,
            "bookings_successful": 0,
            "api_errors": 0,
            "last_check_time": None,
        }
        
        # API key pool management
        self.api_key_pool: Dict[int, List[str]] = {}  # user_id -> [api_keys]
        self.api_key_last_used: Dict[str, float] = {}  # api_key -> timestamp
        self.api_key_errors: Dict[str, int] = {}  # api_key -> error_count
    
    async def initialize(self) -> None:
        """Initialize Redis connection and other resources."""
        try:
            self.redis = aioredis.from_url(
                self.settings.redis.url,
                encoding=self.settings.redis.encoding,
                decode_responses=self.settings.redis.decode_responses,
                socket_timeout=self.settings.redis.socket_timeout,
                socket_connect_timeout=self.settings.redis.socket_connect_timeout,
                retry_on_timeout=self.settings.redis.retry_on_timeout,
                health_check_interval=self.settings.redis.health_check_interval,
            )
            
            # Test Redis connection
            await self.redis.ping()
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown monitoring service gracefully."""
        logger.info("Shutting down monitoring service...")
        self.is_running = False
        
        # Cancel all active tasks
        if self.active_tasks:
            for task_id, task in self.active_tasks.items():
                if not task.done():
                    task.cancel()
                    logger.debug(f"Cancelled monitoring task {task_id}")
            
            # Wait for tasks to complete
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        # Close Redis connection
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
        
        logger.info("Monitoring service shutdown completed")
    
    async def start_monitoring(self) -> None:
        """Start the main monitoring loop."""
        if self.is_running:
            logger.warning("Monitoring service is already running")
            return
        
        self.is_running = True
        logger.info("Starting slot monitoring service...")
        
        try:
            while self.is_running:
                start_time = time.time()
                
                # Get active monitoring tasks
                active_tasks = await self._get_active_monitoring_tasks()
                logger.debug(f"Found {len(active_tasks)} active monitoring tasks")
                
                # Update API key pools
                await self._update_api_key_pools()
                
                # Process tasks concurrently
                if active_tasks:
                    await self._process_tasks_concurrently(active_tasks)
                
                # Update metrics
                self.metrics["last_check_time"] = datetime.utcnow()
                
                # Calculate sleep time to maintain check intervals
                processing_time = time.time() - start_time
                min_interval = min(task.check_interval for task in active_tasks) if active_tasks else 5
                sleep_time = max(0, min_interval - processing_time)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
        except Exception as e:
            logger.error(f"Monitoring service error: {e}")
            self.is_running = False
            raise
    
    async def _get_active_monitoring_tasks(self) -> List[MonitoringTask]:
        """Get all active monitoring tasks from database."""
        async with get_session() as session:
            query = select(MonitoringTask).where(
                MonitoringTask.is_active == True,
                MonitoringTask.is_paused == False,
                MonitoringTask.date_to >= date.today(),
                MonitoringTask.next_check <= datetime.utcnow()
            )
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def _update_api_key_pools(self) -> None:
        """Update API key pools for users."""
        async with get_session() as session:
            # Get all valid API keys
            query = select(APIKey).where(
                APIKey.is_valid == True,
                APIKey.is_active == True
            )
            
            result = await session.execute(query)
            api_keys = result.scalars().all()
            
            # Group by user
            self.api_key_pool.clear()
            for api_key in api_keys:
                if api_key.user_id not in self.api_key_pool:
                    self.api_key_pool[api_key.user_id] = []
                
                try:
                    # Decrypt API key
                    decrypted_key = decrypt_api_key(api_key.encrypted_key, api_key.salt)
                    self.api_key_pool[api_key.user_id].append(decrypted_key)
                except Exception as e:
                    logger.error(f"Failed to decrypt API key {api_key.id}: {e}")
    
    async def _process_tasks_concurrently(self, tasks: List[MonitoringTask]) -> None:
        """Process monitoring tasks concurrently."""
        # Group tasks by check interval for efficient processing
        task_groups = {}
        for task in tasks:
            interval = task.check_interval
            if interval not in task_groups:
                task_groups[interval] = []
            task_groups[interval].append(task)
        
        # Process each group
        coroutines = []
        for interval, group_tasks in task_groups.items():
            # Limit concurrent tasks per group
            semaphore = asyncio.Semaphore(self.settings.monitoring.max_concurrent_requests)
            
            for task in group_tasks:
                coroutine = self._process_single_task_with_semaphore(task, semaphore)
                coroutines.append(coroutine)
        
        # Execute all tasks concurrently
        if coroutines:
            await asyncio.gather(*coroutines, return_exceptions=True)
    
    async def _process_single_task_with_semaphore(
        self, 
        task: MonitoringTask, 
        semaphore: asyncio.Semaphore
    ) -> None:
        """Process single monitoring task with semaphore control."""
        async with semaphore:
            await self._process_single_task(task)
    
    async def _process_single_task(self, task: MonitoringTask) -> None:
        """Process a single monitoring task."""
        task_logger = TaskLogger(task.id, task.user_id, task.warehouse_id)
        
        try:
            start_time = time.time()
            
            # Get API key for this user
            api_key = await self._get_api_key_for_user(task.user_id)
            if not api_key:
                task_logger.warning("No valid API key available for user")
                return
            
            # Check cache first
            cache_key = self._get_cache_key(task)
            cached_slots = await self._get_cached_slots(cache_key)
            
            if cached_slots is None:
                # Fetch fresh data from WB API
                slots = await self._fetch_slots_from_api(task, api_key)
                
                if slots:
                    # Cache the results
                    await self._cache_slots(cache_key, slots)
                    cached_slots = slots
            
            if cached_slots:
                # Process found slots
                await self._process_found_slots(task, cached_slots, task_logger)
            
            # Update task statistics
            await self._update_task_stats(task, success=True)
            
            self.metrics["total_checks"] += 1
            self.metrics["successful_checks"] += 1
            
            # Update next check time
            await self._update_next_check_time(task)
            
            processing_time = time.time() - start_time
            task_logger.debug(f"Task processed successfully in {processing_time:.2f}s")
            
        except Exception as e:
            task_logger.error(f"Error processing task: {e}")
            await self._update_task_stats(task, success=False)
            self.metrics["total_checks"] += 1
            self.metrics["failed_checks"] += 1
    
    async def _get_api_key_for_user(self, user_id: int) -> Optional[str]:
        """Get the best available API key for user."""
        if user_id not in self.api_key_pool:
            return None
        
        user_keys = self.api_key_pool[user_id]
        if not user_keys:
            return None
        
        # Select key with least recent usage and low error count
        best_key = None
        best_score = float('inf')
        
        for key in user_keys:
            error_count = self.api_key_errors.get(key, 0)
            last_used = self.api_key_last_used.get(key, 0)
            
            # Score = error_count * 1000 + seconds_since_last_use
            score = error_count * 1000 + (time.time() - last_used)
            
            if score < best_score:
                best_score = score
                best_key = key
        
        if best_key:
            self.api_key_last_used[best_key] = time.time()
        
        return best_key
    
    def _get_cache_key(self, task: MonitoringTask) -> str:
        """Generate cache key for task."""
        return f"slots:{task.warehouse_id}:{task.supply_type}:{task.delivery_type}:{date.today()}"
    
    async def _get_cached_slots(self, cache_key: str) -> Optional[List[TimeSlot]]:
        """Get cached slots from Redis."""
        if not self.redis:
            return None
        
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                slots_data = json.loads(cached_data)
                return [TimeSlot.parse_obj(slot) for slot in slots_data]
        except Exception as e:
            logger.warning(f"Failed to get cached slots: {e}")
        
        return None
    
    async def _cache_slots(self, cache_key: str, slots: List[TimeSlot]) -> None:
        """Cache slots in Redis."""
        if not self.redis:
            return
        
        try:
            slots_data = [slot.dict() for slot in slots]
            await self.redis.setex(
                cache_key,
                self.settings.monitoring.cache_ttl,
                json.dumps(slots_data)
            )
        except Exception as e:
            logger.warning(f"Failed to cache slots: {e}")
    
    @retry(max_attempts=3, delay=1.0, exceptions=(WBAPIError,))
    async def _fetch_slots_from_api(self, task: MonitoringTask, api_key: str) -> List[TimeSlot]:
        """Fetch slots from WB API."""
        try:
            async with WBAPIClient(api_key) as client:
                response = await client.get_available_slots(
                    warehouse_id=task.warehouse_id,
                    date_from=max(task.date_from, date.today()),
                    date_to=task.date_to,
                    supply_type=SupplyType(task.supply_type),
                    delivery_type=DeliveryType(task.delivery_type)
                )
                
                # Extract all slots from all days
                all_slots = []
                for day in response.days:
                    all_slots.extend(day.slots)
                
                return all_slots
                
        except WBAPIError as e:
            logger.warning(f"WB API error for task {task.id}: {e}")
            
            # Track API key errors
            if api_key in self.api_key_errors:
                self.api_key_errors[api_key] += 1
            else:
                self.api_key_errors[api_key] = 1
            
            self.metrics["api_errors"] += 1
            raise
    
    async def _process_found_slots(
        self, 
        task: MonitoringTask, 
        slots: List[TimeSlot], 
        task_logger: TaskLogger
    ) -> None:
        """Process found slots and handle booking if needed."""
        # Filter slots by coefficient threshold
        qualifying_slots = [
            slot for slot in slots 
            if slot.coefficient <= task.max_coefficient and slot.quota > 0
        ]
        
        if not qualifying_slots:
            task_logger.debug("No qualifying slots found")
            return
        
        self.metrics["slots_found"] += len(qualifying_slots)
        task_logger.info(f"Found {len(qualifying_slots)} qualifying slots")
        
        # Handle based on monitoring mode
        if task.monitoring_mode == MonitoringMode.NOTIFICATION.value:
            await self._send_slot_notification(task, qualifying_slots)
        elif task.monitoring_mode == MonitoringMode.AUTO_BOOKING.value:
            await self._attempt_auto_booking(task, qualifying_slots, task_logger)
    
    async def _send_slot_notification(self, task: MonitoringTask, slots: List[TimeSlot]) -> None:
        """Send notification about found slots."""
        # This will be implemented when we create the bot handlers
        # For now, just log
        logger.info(f"Would send notification for task {task.id} with {len(slots)} slots")
    
    async def _attempt_auto_booking(
        self, 
        task: MonitoringTask, 
        slots: List[TimeSlot], 
        task_logger: TaskLogger
    ) -> None:
        """Attempt automatic booking for qualifying slots."""
        # Check if user can use auto-booking
        async with get_session() as session:
            user_query = select(User).where(User.id == task.user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.can_use_auto_booking():
                task_logger.warning("User cannot use auto-booking feature")
                return
        
        # Get API key
        api_key = await self._get_api_key_for_user(task.user_id)
        if not api_key:
            task_logger.warning("No API key available for booking")
            return
        
        # Try to book the best slot (lowest coefficient)
        best_slot = min(slots, key=lambda s: s.coefficient)
        
        try:
            self.metrics["bookings_attempted"] += 1
            
            async with WBAPIClient(api_key) as client:
                booking_response = await client.create_booking(
                    warehouse_id=task.warehouse_id,
                    booking_date=date.today(),  # For slots today
                    slot_time=best_slot.time,
                    supply_type=SupplyType(task.supply_type),
                    delivery_type=DeliveryType(task.delivery_type)
                )
                
                # Save booking result
                await self._save_booking_result(
                    task=task,
                    slot=best_slot,
                    booking_response=booking_response,
                    status=BookingStatus.CONFIRMED
                )
                
                # Update user trial bookings if applicable
                if not user.is_premium:
                    async with get_session() as session:
                        user.trial_bookings += 1
                        session.add(user)
                        await session.commit()
                
                self.metrics["bookings_successful"] += 1
                task_logger.info(f"Successfully booked slot {best_slot.time}")
                
        except Exception as e:
            task_logger.error(f"Booking failed: {e}")
            
            # Save failed booking result
            await self._save_booking_result(
                task=task,
                slot=best_slot,
                booking_response=None,
                status=BookingStatus.FAILED,
                error_message=str(e)
            )
    
    async def _save_booking_result(
        self,
        task: MonitoringTask,
        slot: TimeSlot,
        booking_response: Optional[Any],
        status: BookingStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Save booking result to database."""
        async with get_session() as session:
            booking_result = BookingResult(
                task_id=task.id,
                booking_date=date.today(),
                slot_time=slot.time,
                coefficient=slot.coefficient,
                status=status.value,
                wb_booking_id=booking_response.booking_id if booking_response else None,
                wb_response=json.dumps(booking_response.dict()) if booking_response else None,
                error_message=error_message
            )
            
            session.add(booking_result)
            await session.commit()
    
    async def _update_task_stats(self, task: MonitoringTask, success: bool) -> None:
        """Update task statistics."""
        async with get_session() as session:
            task.total_checks += 1
            task.last_check = datetime.utcnow()
            
            if not success:
                task.failed_bookings += 1
            
            session.add(task)
            await session.commit()
    
    async def _update_next_check_time(self, task: MonitoringTask) -> None:
        """Update next check time for task."""
        async with get_session() as session:
            next_check = datetime.utcnow() + timedelta(seconds=task.check_interval)
            task.next_check = next_check
            
            session.add(task)
            await session.commit()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current monitoring metrics."""
        return self.metrics.copy()
    
    async def pause_task(self, task_id: int) -> None:
        """Pause monitoring task."""
        async with get_session() as session:
            query = select(MonitoringTask).where(MonitoringTask.id == task_id)
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            
            if task:
                task.is_paused = True
                session.add(task)
                await session.commit()
                logger.info(f"Paused monitoring task {task_id}")
    
    async def resume_task(self, task_id: int) -> None:
        """Resume monitoring task."""
        async with get_session() as session:
            query = select(MonitoringTask).where(MonitoringTask.id == task_id)
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            
            if task:
                task.is_paused = False
                task.next_check = datetime.utcnow()  # Check immediately
                session.add(task)
                await session.commit()
                logger.info(f"Resumed monitoring task {task_id}")


# Global monitoring service instance
monitoring_service = SlotMonitoringService()


async def start_monitoring_service() -> None:
    """Start the global monitoring service."""
    await monitoring_service.initialize()
    await monitoring_service.start_monitoring()


async def stop_monitoring_service() -> None:
    """Stop the global monitoring service."""
    await monitoring_service.shutdown()
