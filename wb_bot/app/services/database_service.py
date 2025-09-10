"""
Database service for managing users, API keys, and monitoring tasks.

Provides high-level database operations with proper error handling,
validation, and business logic.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from ..database.connection import get_session
from ..database.models import (
    User, APIKey, MonitoringTask, BookingResult, BrowserSession,
    SupplyType, DeliveryType, MonitoringMode, BookingStatus
)
from ..utils.encryption import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)


class DatabaseService:
    """High-level database service for bot operations."""
    
    async def get_or_create_user(self, telegram_id: int, **kwargs) -> User:
        """Get existing user or create new one."""
        async with get_session() as session:
            # Try to get existing user
            stmt = select(User).where(User.id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Update last activity
                user.last_activity = datetime.utcnow()
                await session.commit()
                return user
            
            # Create new user
            user_data = {
                'id': telegram_id,
                'username': kwargs.get('username'),
                'first_name': kwargs.get('first_name'),
                'last_name': kwargs.get('last_name'),
                'language_code': kwargs.get('language_code', 'ru'),
                'last_activity': datetime.utcnow()
            }
            
            user = User(**user_data)
            session.add(user)
            await session.commit()
            
            logger.info(f"Created new user: {telegram_id}")
            return user
    
    async def get_user_api_keys(self, user_id: int) -> List[APIKey]:
        """Get all active API keys for user."""
        async with get_session() as session:
            stmt = (
                select(APIKey)
                .where(and_(APIKey.user_id == user_id, APIKey.is_active == True))
                .order_by(APIKey.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def add_api_key(
        self, 
        user_id: int, 
        api_key: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> APIKey:
        """Add new API key for user."""
        async with get_session() as session:
            # Check if user exists
            user_stmt = select(User).where(User.id == user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Check API key limit
            count_stmt = (
                select(APIKey)
                .where(and_(APIKey.user_id == user_id, APIKey.is_active == True))
            )
            count_result = await session.execute(count_stmt)
            existing_keys = list(count_result.scalars().all())
            
            if len(existing_keys) >= 5:  # Max 5 API keys per user
                raise ValueError("Maximum number of API keys reached (5)")
            
            # Encrypt API key
            encrypted_key, salt = encrypt_api_key(api_key)
            
            # Create API key record
            api_key_record = APIKey(
                user_id=user_id,
                encrypted_key=encrypted_key,
                salt=salt,
                name=name or f"API ключ {len(existing_keys) + 1}",
                description=description
            )
            
            session.add(api_key_record)
            await session.commit()
            
            logger.info(f"Added API key for user {user_id}: {api_key_record.name}")
            return api_key_record
    
    async def get_decrypted_api_keys(self, user_id: int) -> List[str]:
        """Get decrypted API keys for user."""
        api_keys = await self.get_user_api_keys(user_id)
        decrypted_keys = []
        
        for api_key in api_keys:
            try:
                decrypted = decrypt_api_key(api_key.encrypted_key, api_key.salt)
                decrypted_keys.append(decrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt API key {api_key.id}: {e}")
                continue
        
        return decrypted_keys
    
    async def remove_api_key(self, user_id: int, api_key_id: int) -> bool:
        """Remove API key for user."""
        async with get_session() as session:
            stmt = (
                update(APIKey)
                .where(and_(APIKey.id == api_key_id, APIKey.user_id == user_id))
                .values(is_active=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Removed API key {api_key_id} for user {user_id}")
                return True
            return False
    
    async def create_monitoring_task(
        self,
        user_id: int,
        warehouse_id: int,
        warehouse_name: str,
        date_from: date,
        date_to: date,
        **kwargs
    ) -> MonitoringTask:
        """Create new monitoring task."""
        async with get_session() as session:
            # Check if user exists
            user_stmt = select(User).where(User.id == user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Check for duplicate task
            existing_stmt = (
                select(MonitoringTask)
                .where(and_(
                    MonitoringTask.user_id == user_id,
                    MonitoringTask.warehouse_id == warehouse_id,
                    MonitoringTask.date_from == date_from,
                    MonitoringTask.date_to == date_to,
                    MonitoringTask.is_active == True
                ))
            )
            existing_result = await session.execute(existing_stmt)
            existing_task = existing_result.scalar_one_or_none()
            
            if existing_task:
                raise ValueError("Monitoring task for this warehouse and dates already exists")
            
            # Create monitoring task
            task_data = {
                'user_id': user_id,
                'warehouse_id': warehouse_id,
                'warehouse_name': warehouse_name,
                'date_from': date_from,
                'date_to': date_to,
                'check_interval': kwargs.get('check_interval', user.default_check_interval),
                'max_coefficient': kwargs.get('max_coefficient', user.default_max_coefficient),
                'supply_type': kwargs.get('supply_type', user.default_supply_type),
                'delivery_type': kwargs.get('delivery_type', user.default_delivery_type),
                'monitoring_mode': kwargs.get('monitoring_mode', user.default_monitoring_mode)
            }
            
            task = MonitoringTask(**task_data)
            session.add(task)
            await session.commit()
            
            logger.info(f"Created monitoring task {task.id} for user {user_id}")
            return task
    
    async def get_active_monitoring_tasks(self, user_id: Optional[int] = None) -> List[MonitoringTask]:
        """Get active monitoring tasks."""
        async with get_session() as session:
            stmt = (
                select(MonitoringTask)
                .where(MonitoringTask.is_active == True)
                .options(selectinload(MonitoringTask.user))
            )
            
            if user_id:
                stmt = stmt.where(MonitoringTask.user_id == user_id)
            
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    async def update_monitoring_task(self, task_id: int, **kwargs) -> bool:
        """Update monitoring task."""
        async with get_session() as session:
            stmt = (
                update(MonitoringTask)
                .where(MonitoringTask.id == task_id)
                .values(**kwargs)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            return result.rowcount > 0
    
    async def deactivate_monitoring_task(self, task_id: int, user_id: Optional[int] = None) -> bool:
        """Deactivate monitoring task."""
        async with get_session() as session:
            conditions = [MonitoringTask.id == task_id]
            if user_id:
                conditions.append(MonitoringTask.user_id == user_id)
            
            stmt = (
                update(MonitoringTask)
                .where(and_(*conditions))
                .values(is_active=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Deactivated monitoring task {task_id}")
                return True
            return False
    
    async def create_booking_result(
        self,
        task_id: int,
        booking_date: date,
        **kwargs
    ) -> BookingResult:
        """Create booking result record."""
        async with get_session() as session:
            result_data = {
                'task_id': task_id,
                'booking_date': booking_date,
                'slot_time': kwargs.get('slot_time'),
                'coefficient': kwargs.get('coefficient'),
                'wb_booking_id': kwargs.get('wb_booking_id'),
                'wb_response': kwargs.get('wb_response'),
                'status': kwargs.get('status', BookingStatus.PENDING),
                'api_key_id': kwargs.get('api_key_id')
            }
            
            booking_result = BookingResult(**result_data)
            session.add(booking_result)
            await session.commit()
            
            logger.info(f"Created booking result {booking_result.id} for task {task_id}")
            return booking_result
    
    async def update_booking_result(self, result_id: int, **kwargs) -> bool:
        """Update booking result."""
        async with get_session() as session:
            stmt = (
                update(BookingResult)
                .where(BookingResult.id == result_id)
                .values(**kwargs)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            return result.rowcount > 0
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics."""
        async with get_session() as session:
            # Get user with API keys
            user_stmt = (
                select(User)
                .where(User.id == user_id)
                .options(selectinload(User.api_keys))
            )
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                return {}
            
            # Get monitoring tasks count
            tasks_stmt = (
                select(MonitoringTask)
                .where(and_(MonitoringTask.user_id == user_id, MonitoringTask.is_active == True))
            )
            tasks_result = await session.execute(tasks_stmt)
            active_tasks = list(tasks_result.scalars().all())
            
            # Get booking results count
            booking_stmt = (
                select(BookingResult)
                .join(MonitoringTask)
                .where(MonitoringTask.user_id == user_id)
            )
            booking_result = await session.execute(booking_stmt)
            booking_results = list(booking_result.scalars().all())
            
            successful_bookings = len([r for r in booking_results if r.is_successful()])
            
            return {
                'user': user,
                'api_keys_count': len([k for k in user.api_keys if k.is_active]),
                'active_tasks_count': len(active_tasks),
                'total_bookings': len(booking_results),
                'successful_bookings': successful_bookings,
                'trial_bookings_left': max(0, 2 - user.trial_bookings) if not user.is_premium else None
            }
    
    async def cleanup_expired_tasks(self) -> int:
        """Remove expired monitoring tasks."""
        async with get_session() as session:
            today = date.today()
            stmt = (
                update(MonitoringTask)
                .where(and_(
                    MonitoringTask.date_to < today,
                    MonitoringTask.is_active == True
                ))
                .values(is_active=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Deactivated {result.rowcount} expired monitoring tasks")
            
            return result.rowcount
    
    # ==================== BROWSER SESSION MANAGEMENT ====================
    
    async def get_or_create_browser_session(self, user_id: int, phone_number: str = None) -> Optional[BrowserSession]:
        """Получить или создать браузерную сессию для пользователя."""
        try:
            async with get_session() as session:
                # Сначала ищем существующую сессию
                stmt = select(BrowserSession).where(BrowserSession.user_id == user_id)
                result = await session.execute(stmt)
                browser_session = result.scalar_one_or_none()
                
                if browser_session:
                    logger.info(f"Found existing browser session for user {user_id}")
                    return browser_session
                
                # Создаем новую сессию
                import hashlib
                import time
                fingerprint = hashlib.md5(f"{user_id}_{time.time()}".encode()).hexdigest()[:20]
                
                browser_session = BrowserSession(
                    user_id=user_id,
                    phone_number=phone_number,
                    session_valid=True,
                    user_data_dir=f"wb_user_data_{user_id}",
                    cookies_file=f"wb_cookies_{user_id}.json",
                    browser_fingerprint=fingerprint
                )
                
                session.add(browser_session)
                await session.commit()
                await session.refresh(browser_session)
                
                logger.info(f"Created new browser session for user {user_id}")
                return browser_session
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_or_create_browser_session: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_or_create_browser_session: {e}")
            return None
    
    async def update_browser_session_login_success(self, user_id: int, phone_number: str) -> bool:
        """Обновить сессию после успешного входа."""
        try:
            async with get_session() as session:
                stmt = select(BrowserSession).where(BrowserSession.user_id == user_id)
                result = await session.execute(stmt)
                browser_session = result.scalar_one_or_none()
                
                if not browser_session:
                    # Создаем новую если не существует
                    browser_session = await self.get_or_create_browser_session(user_id, phone_number)
                    if not browser_session:
                        return False
                
                # Обновляем данные успешного входа
                browser_session.mark_login_success(phone_number)
                browser_session.login_attempts = 0  # Сбрасываем счетчик неудачных попыток
                
                await session.commit()
                logger.info(f"Updated browser session login success for user {user_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_browser_session_login_success: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in update_browser_session_login_success: {e}")
            return False
    
    async def update_browser_session_login_failed(self, user_id: int) -> bool:
        """Обновить сессию после неудачной попытки входа."""
        try:
            async with get_session() as session:
                stmt = select(BrowserSession).where(BrowserSession.user_id == user_id)
                result = await session.execute(stmt)
                browser_session = result.scalar_one_or_none()
                
                if not browser_session:
                    # Создаем новую если не существует
                    browser_session = await self.get_or_create_browser_session(user_id)
                    if not browser_session:
                        return False
                
                # Обновляем данные неудачной попытки
                browser_session.mark_login_failed()
                
                await session.commit()
                logger.info(f"Updated browser session login failed for user {user_id} (attempts: {browser_session.login_attempts})")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in update_browser_session_login_failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in update_browser_session_login_failed: {e}")
            return False
    
    async def is_browser_session_valid(self, user_id: int) -> bool:
        """Проверить валидность браузерной сессии."""
        try:
            async with get_session() as session:
                stmt = select(BrowserSession).where(BrowserSession.user_id == user_id)
                result = await session.execute(stmt)
                browser_session = result.scalar_one_or_none()
                
                if not browser_session:
                    logger.info(f"No browser session found for user {user_id}")
                    return False
                
                # Проверяем валидность и не истекла ли сессия
                is_valid = browser_session.session_valid and not browser_session.is_session_expired()
                
                logger.info(f"Browser session for user {user_id}: valid={browser_session.session_valid}, expired={browser_session.is_session_expired()}, result={is_valid}")
                return is_valid
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in is_browser_session_valid: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in is_browser_session_valid: {e}")
            return False
    
    async def get_browser_session_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные браузерной сессии."""
        try:
            async with get_session() as session:
                stmt = select(BrowserSession).where(BrowserSession.user_id == user_id)
                result = await session.execute(stmt)
                browser_session = result.scalar_one_or_none()
                
                if not browser_session:
                    return None
                
                return {
                    'user_data_dir': browser_session.user_data_dir,
                    'cookies_file': browser_session.cookies_file,
                    'phone_number': browser_session.phone_number,
                    'session_valid': browser_session.session_valid,
                    'wb_login_success': browser_session.wb_login_success,
                    'last_successful_login': browser_session.last_successful_login,
                    'login_attempts': browser_session.login_attempts
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_browser_session_data: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_browser_session_data: {e}")
            return None


# Global database service instance
db_service = DatabaseService()

