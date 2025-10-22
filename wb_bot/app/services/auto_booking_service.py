"""
Сервис автоматического бронирования поставок (Автоловля).
Полностью переписанная логика для надежной работы автобронирования.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import traceback

from ..utils.logger import get_logger
from .wb_supplies_api import WBSuppliesAPIClient
from .browser_manager import browser_manager
from .browser_automation import WBBrowserAutomationPro

logger = get_logger(__name__)


@dataclass
class AutoBookingSession:
    """Сессия автобронирования"""
    user_id: int
    supply_id: str
    supply_name: str
    warehouse_id: int
    warehouse_name: str
    date_from: str
    date_to: str
    max_coefficient: Optional[int] = None
    check_interval: int = 10  # Интервал проверки в секундах
    status: str = "active"  # active, stopped, completed, error
    created_at: datetime = None
    last_check: Optional[datetime] = None
    checks_count: int = 0
    mode: str = "api"  # api или browser
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class AutoBookingService:
    """
    Сервис автоматического бронирования (автоловли) поставок.
    
    Поддерживает два режима работы:
    1. API mode - быстрая проверка через API WB
    2. Browser mode - автоматизация через браузер (как расширение Chrome)
    """
    
    def __init__(self):
        self.active_sessions: Dict[int, AutoBookingSession] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        
    async def start_auto_booking(
        self,
        user_id: int,
        supply_id: str,
        supply_name: str,
        warehouse_id: int,
        warehouse_name: str,
        date_from: str,
        date_to: str,
        max_coefficient: Optional[int] = None,
        check_interval: int = 10,
        mode: str = "api",
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ) -> bool:
        """
        Запустить автобронирование для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            supply_id: ID поставки для бронирования
            supply_name: Название поставки
            warehouse_id: ID склада
            warehouse_name: Название склада
            date_from: Начальная дата поиска (YYYY-MM-DD)
            date_to: Конечная дата поиска (YYYY-MM-DD)
            max_coefficient: Максимальный коэффициент (None = любой)
            check_interval: Интервал проверки в секундах
            mode: Режим работы ("api" или "browser")
            on_success: Callback при успешном бронировании
            on_error: Callback при ошибке
            
        Returns:
            True если запущено успешно, False если уже запущено
        """
        # Проверяем, не запущено ли уже автобронирование для этого пользователя
        if user_id in self.active_sessions:
            logger.warning(f"Автобронирование для пользователя {user_id} уже запущено")
            return False
        
        # Создаем сессию
        session = AutoBookingSession(
            user_id=user_id,
            supply_id=supply_id,
            supply_name=supply_name,
            warehouse_id=warehouse_id,
            warehouse_name=warehouse_name,
            date_from=date_from,
            date_to=date_to,
            max_coefficient=max_coefficient,
            check_interval=check_interval,
            mode=mode
        )
        
        self.active_sessions[user_id] = session
        
        logger.info(
            f"🚀 Запуск автобронирования для пользователя {user_id}\n"
            f"   Поставка: {supply_name} ({supply_id})\n"
            f"   Склад: {warehouse_name} ({warehouse_id})\n"
            f"   Период: {date_from} - {date_to}\n"
            f"   Макс. коэфф: {max_coefficient}\n"
            f"   Режим: {mode}\n"
            f"   Интервал: {check_interval}с"
        )
        
        # Запускаем фоновую задачу
        if mode == "browser":
            task = asyncio.create_task(
                self._run_browser_mode(session, on_success, on_error)
            )
        else:
            task = asyncio.create_task(
                self._run_api_mode(session, on_success, on_error)
            )
        
        self.tasks[user_id] = task
        
        return True
    
    async def stop_auto_booking(self, user_id: int) -> bool:
        """
        Остановить автобронирование для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если остановлено, False если не было запущено
        """
        if user_id not in self.active_sessions:
            return False
        
        # Меняем статус
        self.active_sessions[user_id].status = "stopped"
        
        # Отменяем задачу
        if user_id in self.tasks:
            task = self.tasks[user_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.tasks[user_id]
        
        # Удаляем сессию
        del self.active_sessions[user_id]
        
        logger.info(f"⏹️ Автобронирование остановлено для пользователя {user_id}")
        
        return True
    
    def get_session(self, user_id: int) -> Optional[AutoBookingSession]:
        """Получить активную сессию пользователя"""
        return self.active_sessions.get(user_id)
    
    def is_active(self, user_id: int) -> bool:
        """Проверить, активно ли автобронирование для пользователя"""
        return user_id in self.active_sessions
    
    async def _run_api_mode(
        self, 
        session: AutoBookingSession,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ):
        """
        Режим автобронирования через API.
        Быстро проверяет доступные слоты и бронирует через API.
        """
        user_id = session.user_id
        
        try:
            logger.info(f"🔄 Запущен API режим автобронирования для пользователя {user_id}")
            
            # Получаем API ключ пользователя
            from .database_service import db_service
            api_keys = await db_service.get_decrypted_api_keys(user_id)
            
            if not api_keys:
                error_msg = "❌ Нет API ключей для автобронирования"
                logger.error(error_msg)
                session.status = "error"
                if on_error:
                    await on_error(error_msg)
                return
            
            api_key = api_keys[0]
            
            # Основной цикл проверки
            while session.status == "active":
                try:
                    session.last_check = datetime.now()
                    session.checks_count += 1
                    
                    logger.debug(f"🔍 Проверка #{session.checks_count} для пользователя {user_id}")
                    
                    # Проверяем доступные слоты через API
                    async with WBSuppliesAPIClient(api_key) as api_client:
                        slots = await api_client.get_available_slots(
                            warehouse_id=session.warehouse_id,
                            date_from=session.date_from,
                            date_to=session.date_to
                        )
                    
                    if not slots:
                        logger.debug(f"   Слоты не найдены. Ожидание {session.check_interval}с...")
                        await asyncio.sleep(session.check_interval)
                        continue
                    
                    logger.info(f"✅ Найдено {len(slots)} слотов!")
                    
                    # Фильтруем по коэффициенту если задан
                    suitable_slots = []
                    for slot in slots:
                        coefficient = slot.get('coefficient', 999)
                        
                        # Проверяем коэффициент
                        if session.max_coefficient is not None:
                            if coefficient > session.max_coefficient:
                                continue
                        
                        suitable_slots.append(slot)
                    
                    if not suitable_slots:
                        logger.debug(
                            f"   Подходящих слотов не найдено "
                            f"(макс. коэфф: {session.max_coefficient})"
                        )
                        await asyncio.sleep(session.check_interval)
                        continue
                    
                    # Берем лучший слот (с минимальным коэффициентом)
                    best_slot = min(suitable_slots, key=lambda x: x.get('coefficient', 999))
                    slot_date = best_slot.get('date')
                    slot_time = best_slot.get('time', '')
                    slot_coefficient = best_slot.get('coefficient', 0)
                    
                    logger.info(
                        f"🎯 Найден подходящий слот!\n"
                        f"   Дата: {slot_date}\n"
                        f"   Время: {slot_time}\n"
                        f"   Коэффициент: {slot_coefficient}x"
                    )
                    
                    # Пытаемся забронировать
                    success = await self._book_slot_via_api(
                        api_key=api_key,
                        supply_id=session.supply_id,
                        warehouse_id=session.warehouse_id,
                        date=slot_date,
                        time=slot_time
                    )
                    
                    if success:
                        logger.info(f"🎉 ПОСТАВКА УСПЕШНО ЗАБРОНИРОВАНА!")
                        session.status = "completed"
                        
                        if on_success:
                            await on_success({
                                'supply_id': session.supply_id,
                                'supply_name': session.supply_name,
                                'warehouse_name': session.warehouse_name,
                                'date': slot_date,
                                'time': slot_time,
                                'coefficient': slot_coefficient,
                                'checks_count': session.checks_count
                            })
                        
                        break
                    else:
                        logger.warning(f"⚠️ Не удалось забронировать слот. Продолжаем поиск...")
                        await asyncio.sleep(session.check_interval)
                        
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"❌ Ошибка при проверке слотов: {e}")
                    logger.debug(traceback.format_exc())
                    await asyncio.sleep(session.check_interval)
            
            logger.info(f"🏁 Автобронирование завершено для пользователя {user_id}")
            
        except asyncio.CancelledError:
            logger.info(f"⏹️ Автобронирование отменено для пользователя {user_id}")
            session.status = "stopped"
        except Exception as e:
            error_msg = f"❌ Критическая ошибка автобронирования: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            session.status = "error"
            
            if on_error:
                await on_error(error_msg)
        finally:
            # Очистка
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
            if user_id in self.tasks:
                del self.tasks[user_id]
    
    async def _run_browser_mode(
        self,
        session: AutoBookingSession,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ):
        """
        Режим автобронирования через браузер.
        Использует браузерную автоматизацию как Chrome расширение.
        """
        user_id = session.user_id
        browser = None
        
        try:
            logger.info(f"🌐 Запущен браузерный режим автобронирования для пользователя {user_id}")
            
            # Получаем браузер
            browser = await browser_manager.get_browser(
                user_id=user_id,
                headless=False,  # Видимый браузер для отладки
                debug_mode=True
            )
            
            if not browser:
                error_msg = "❌ Не удалось получить браузер"
                logger.error(error_msg)
                session.status = "error"
                if on_error:
                    await on_error(error_msg)
                return
            
            # Создаем автоматизацию
            automation = WBBrowserAutomationPro(browser['page'])
            
            # Настраиваем фильтры для автоловли
            filters = {
                'dateFrom': session.date_from,
                'dateTo': session.date_to,
            }
            
            if session.max_coefficient is not None:
                filters['maxCoefficient'] = session.max_coefficient
            
            logger.info(f"🎯 Запуск автоловли через браузер с фильтрами: {filters}")
            
            # Запускаем автоловлю
            # Интервал в миллисекундах
            interval_ms = session.check_interval * 1000
            
            result = await automation.auto_catch_supply(
                filters=filters,
                interval_ms=interval_ms
            )
            
            if result:
                logger.info(f"🎉 Поставка успешно забронирована через браузер!")
                session.status = "completed"
                
                if on_success:
                    await on_success({
                        'supply_id': session.supply_id,
                        'supply_name': session.supply_name,
                        'warehouse_name': session.warehouse_name,
                        'mode': 'browser'
                    })
            else:
                logger.warning(f"⚠️ Автоловля через браузер завершилась без результата")
                session.status = "stopped"
                
        except asyncio.CancelledError:
            logger.info(f"⏹️ Браузерное автобронирование отменено для пользователя {user_id}")
            session.status = "stopped"
        except Exception as e:
            error_msg = f"❌ Ошибка браузерного автобронирования: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            session.status = "error"
            
            if on_error:
                await on_error(error_msg)
        finally:
            # Закрываем браузер
            if browser:
                await browser_manager.close_browser(user_id)
            
            # Очистка
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
            if user_id in self.tasks:
                del self.tasks[user_id]
    
    async def _book_slot_via_api(
        self,
        api_key: str,
        supply_id: str,
        warehouse_id: int,
        date: str,
        time: str = ""
    ) -> bool:
        """
        Забронировать слот через API.
        
        Returns:
            True если успешно, False если ошибка
        """
        try:
            async with WBSuppliesAPIClient(api_key) as api_client:
                # Используем метод для бронирования поставки
                result = await api_client.book_supply(
                    supply_id=supply_id,
                    warehouse_id=warehouse_id,
                    date=date,
                    time=time
                )
                
                return result is not None and result.get('success', False)
                
        except Exception as e:
            logger.error(f"Ошибка бронирования через API: {e}")
            return False


# Глобальный экземпляр сервиса
auto_booking_service = AutoBookingService()

