"""
Менеджер для управления параллельным бронированием нескольких поставок
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from ..utils.logger import get_logger
from .browser_manager import BrowserManager
from .browser_automation import WBBrowserAutomationPro

logger = get_logger(__name__)


@dataclass
class BookingTask:
    """Задача бронирования."""
    id: str
    supply: Dict[str, Any]
    user_id: int
    params: Dict[str, Any]
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    browser_id: Optional[str] = None
    page_reference: Optional[Any] = None  # Ссылка на Playwright Page для закрытия


class MultiBookingManager:
    """Менеджер параллельного бронирования поставок."""
    
    def __init__(self, browser_manager: BrowserManager):
        self.browser_manager = browser_manager
        self.active_bookings: Dict[str, Dict[str, Any]] = {}  # session_id -> booking_info
        self.booking_tasks: Dict[str, List[BookingTask]] = {}  # session_id -> tasks
        self._progress_callbacks: Dict[str, Callable] = {}
        
    async def start_multi_booking(
        self, 
        user_id: int, 
        supplies: List[Dict[str, Any]], 
        booking_params: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Запускает параллельное бронирование нескольких поставок.
        
        Args:
            user_id: ID пользователя
            supplies: Список поставок для бронирования
            booking_params: Параметры бронирования (дата, коэффициент и т.д.)
            progress_callback: Функция для уведомлений о прогрессе
            
        Returns:
            session_id: Уникальный ID сессии мультибронирования
        """
        session_id = str(uuid.uuid4())
        
        logger.info(f"🎯 Запуск мультибронирования для пользователя {user_id}")
        logger.info(f"📦 Поставок для бронирования: {len(supplies)}")
        logger.info(f"🔑 Session ID: {session_id}")
        
        # КРИТИЧНО: Убеждаемся что у пользователя есть исходный браузер!
        # ДЛЯ РАЗРАБОТКИ: headless=False чтобы видеть браузер!
        source_browser = await self.browser_manager.get_browser(
            user_id=user_id, 
            headless=False,  # 👀 ВИДИМЫЙ БРАУЗЕР ДЛЯ ОТЛАДКИ!
            debug_mode=True,  # 🐛 РЕЖИМ ОТЛАДКИ!
            browser_type="firefox"
        )
        
        if not source_browser:
            raise Exception(f"Не удалось создать исходный браузер для пользователя {user_id}")
        
        logger.info(f"✅ Исходный браузер пользователя {user_id} готов для клонирования")
        
        # Создаем задачи бронирования
        tasks = []
        for supply in supplies:
            task = BookingTask(
                id=str(uuid.uuid4()),
                supply=supply,
                user_id=user_id,
                params=booking_params.copy()
            )
            tasks.append(task)
        
        # Сохраняем информацию о сессии
        self.active_bookings[session_id] = {
            "user_id": user_id,
            "start_time": datetime.now(),
            "total_tasks": len(tasks),
            "completed_tasks": 0,
            "failed_tasks": 0,
            "status": "starting"
        }
        self.booking_tasks[session_id] = tasks
        
        if progress_callback:
            self._progress_callbacks[session_id] = progress_callback
        
        # Запускаем последовательное бронирование
        asyncio.create_task(self._execute_parallel_booking(session_id))
        
        return session_id
    
    async def _execute_parallel_booking(self, session_id: str):
        """Выполняет последовательное бронирование."""
        try:
            tasks = self.booking_tasks[session_id]
            booking_info = self.active_bookings[session_id]
            booking_info["status"] = "in_progress"
            
            logger.info(f"🚀 Начинаю последовательное выполнение {len(tasks)} задач бронирования")
            
            # Уведомляем о начале
            await self._notify_progress(session_id, "🚀 Запускаю браузеры для мультибронирования...")
            
            # Выполняем задачи ПОСЛЕДОВАТЕЛЬНО (по очереди)
            logger.info(f"🚀 Запускаю {len(tasks)} задач бронирования ПО ОЧЕРЕДИ")
            for i, task in enumerate(tasks):
                task_num = i + 1
                total_tasks = len(tasks)
                supply_name = task.supply.get('name', f"Поставка #{task.supply.get('id')}")
                
                logger.info(f"📋 ЭТАП {task_num}/{total_tasks}: Обрабатываю {supply_name}")
                
                # УВЕДОМЛЯЕМ О НАЧАЛЕ КАЖДОЙ ПОСТАВКИ
                await self._notify_progress(session_id, 
                    f"🔄 Поставка {task_num}/{total_tasks}\n📦 {supply_name[:30]}\n⏳ Открываю браузер...")
                
                # ВЫПОЛНЯЕМ БРОНИРОВАНИЕ
                try:
                    await self._execute_single_booking(session_id, task)
                    logger.info(f"📊 ПОСЛЕ _execute_single_booking: task.status={task.status}, task.result={bool(task.result)}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке поставки {task_num}: {e}")
                    task.status = "failed"
                    task.error = str(e)
                
                # СРАЗУ ПОСЛЕ БРОНИРОВАНИЯ - ПРОВЕРЯЕМ РЕЗУЛЬТАТ И УВЕДОМЛЯЕМ!
                # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: если статус не определился, но result есть
                if task.result and task.result.get("success", False) and task.status != "completed":
                    logger.warning(f"⚠️ Исправляю статус для {supply_name}: было {task.status}, стало completed")
                    task.status = "completed"
                
                if task.status == "completed" and task.result:
                    booking_result = task.result
                    booking_date = booking_result.get("booking_date", "Неизвестно")
                    warehouse_name = booking_result.get("warehouse_name", "Неизвестен") 
                    coefficient = booking_result.get("coefficient", "Неизвестен")
                    new_supply_id = booking_result.get("new_supply_id")
                    supply_id = task.supply.get("id")
                    
                    # ФОРМИРУЕМ ДЕТАЛЬНОЕ СООБЩЕНИЕ КАК В ОДИНОЧНОМ РЕЖИМЕ
                    success_message = (
                        f"🎉 УСПЕХ {task_num}/{total_tasks}!\n\n"
                        f"📦 <b>{supply_name[:30]}</b>\n"
                        f"🆔 ID: <code>{supply_id}</code>\n"
                    )
                    
                    # Добавляем новый ID если найден
                    if new_supply_id and new_supply_id != str(supply_id):
                        success_message += f"🆔 <b>Новый ID:</b> <code>{new_supply_id}</code>\n"
                    
                    success_message += (
                        f"\n📅 <b>Дата:</b> {booking_date}\n"
                        f"🏬 <b>Склад:</b> {warehouse_name}\n"
                        f"📊 <b>Коэффициент:</b> {coefficient}\n\n"
                        f"✅ Бронирование завершено!"
                    )
                    
                    logger.info(f"✅ ПОСТАВКА {task_num} ЗАБРОНИРОВАНА: {supply_name}")
                    await self._notify_progress(session_id, success_message)
                    
                elif task.status == "failed":
                    error_msg = task.error or "Неизвестная ошибка"
                    fail_message = (
                        f"❌ ОШИБКА {task_num}/{total_tasks}\n"
                        f"📦 {supply_name[:25]}\n"
                        f"💥 {error_msg[:50]}"
                    )
                    
                    logger.warning(f"❌ ПОСТАВКА {task_num} НЕ ЗАБРОНИРОВАНА: {supply_name}")
                    await self._notify_progress(session_id, fail_message)
                
                else:
                    # НЕОПРЕДЕЛЕННЫЙ СТАТУС - логируем как проблему
                    logger.error(f"❓ НЕОПРЕДЕЛЕННЫЙ СТАТУС для поставки {task_num}: status={task.status}, result={bool(task.result)}")
                    unknown_message = (
                        f"❓ НЕОПРЕДЕЛЕННЫЙ РЕЗУЛЬТАТ {task_num}/{total_tasks}\n"
                        f"📦 {supply_name[:25]}\n"
                        f"🤷 Статус: {task.status}"
                    )
                    await self._notify_progress(session_id, unknown_message)
                
                # ПАУЗА МЕЖДУ ПОСТАВКАМИ ТОЛЬКО ЕСЛИ НЕ ПОСЛЕДНЯЯ
                if task_num < total_tasks:
                    await self._notify_progress(session_id, 
                        f"⏳ Переходим к поставке {task_num + 1}/{total_tasks}...")
                    await asyncio.sleep(2)  # Небольшая пауза между поставками
            
            # Финализируем сессию
            await self._finalize_booking_session(session_id)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в мультибронировании {session_id}: {e}")
            await self._notify_progress(session_id, f"❌ Критическая ошибка: {str(e)}")
            
            # Помечаем сессию как завершенную с ошибкой
            if session_id in self.active_bookings:
                self.active_bookings[session_id]["status"] = "failed"
    
    async def _execute_single_booking(self, session_id: str, task: BookingTask):
        """Выполняет бронирование одной поставки в отдельной вкладке."""
        try:
            task.status = "in_progress"
            supply = task.supply
            supply_id = supply.get("id")
            supply_name = supply.get("name", f"Поставка #{supply_id}")
            
            logger.info(f"🎯 Начинаю бронирование поставки {supply_id} ({supply_name})")
            
            # Получаем исходный браузер пользователя
            source_browser = self.browser_manager._browsers.get(task.user_id)
            if not source_browser:
                raise Exception(f"Исходный браузер пользователя {task.user_id} не найден!")
            
            # Создаем новую вкладку в том же браузере (ТОЛЬКО ДЛЯ МУЛЬТИБРОНИРОВАНИЯ!)
            logger.info(f"📄 МУЛЬТИБРОНИРОВАНИЕ: Создаю новую вкладку для поставки {supply_id}")
            new_page = await source_browser.context.new_page()
            
            # Сохраняем ссылку на вкладку для закрытия
            task.page_reference = new_page  # Сохраняем прямую ссылку на страницу
            task.browser_id = id(new_page)  # Используем id объекта как уникальный идентификатор
            
            # 🌐 КРИТИЧНО: Переходим на страницу поставки В НОВОЙ ВКЛАДКЕ!
            supply_url = f"https://suppliers.wildberries.ru/supplies-management/all-supplies/supply-detail/transportation-task?preorderId={supply_id}"
            logger.info(f"🌐 Переходим к поставке {supply_id} в новой вкладке: {supply_url}")
            await new_page.goto(supply_url, wait_until="domcontentloaded", timeout=30000)
            
            # Даём время на загрузку
            await asyncio.sleep(3)
            
            logger.info(f"✅ Вкладка создана для поставки {supply_id}")
            
            # Создаем временный объект браузера для этой вкладки
            # Копируем ВСЕ атрибуты исходного браузера
            temp_browser = type('TempBrowser', (), {})()
            
            # Копируем все атрибуты из исходного браузера
            for attr_name in dir(source_browser):
                if not attr_name.startswith('_'):  # Пропускаем приватные атрибуты
                    try:
                        setattr(temp_browser, attr_name, getattr(source_browser, attr_name))
                    except:
                        pass  # Игнорируем ошибки копирования
            
            # Заменяем только page на новую вкладку
            temp_browser.page = new_page
            
            # Выполняем бронирование в новой вкладке
            logger.info(f"🚀 ВЫЗЫВАЮ book_supply_by_id для поставки {supply_id} с параметрами: {task.params}")
            booking_result = await temp_browser.book_supply_by_id(
                supply_id=str(supply_id),
                preorder_id=str(supply_id),  # Используем supply_id как preorder_id
                **task.params
            )
            
            logger.info(f"📋 ПОЛУЧИЛ РЕЗУЛЬТАТ book_supply_by_id для {supply_id}: {booking_result}")
            task.result = booking_result
            
            if booking_result and booking_result.get("success", False):
                task.status = "completed"
                logger.info(f"✅ Поставка {supply_id} успешно забронирована")
                
                # ДЕТАЛИ БРОНИРОВАНИЯ (как в одиночном режиме)
                booking_date = booking_result.get("booking_date", "Неизвестно") 
                warehouse_name = booking_result.get("warehouse_name", "Неизвестен")
                coefficient = booking_result.get("coefficient", "Неизвестен")
                new_supply_id = booking_result.get("new_supply_id")
                
                logger.info(f"📊 ДЕТАЛИ БРОНИРОВАНИЯ {supply_id}: дата={booking_date}, склад={warehouse_name}, коэф={coefficient}")
                
            elif booking_result:
                task.status = "failed" 
                task.error = booking_result.get("message", "Неизвестная ошибка")
                logger.warning(f"❌ Не удалось забронировать поставку {supply_id}: {task.error}")
            else:
                task.status = "failed"
                task.error = "book_supply_by_id вернул None"
                logger.error(f"❌ book_supply_by_id вернул None для поставки {supply_id}")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"❌ Ошибка бронирования поставки {supply_id}: {e}")
            
        finally:
            # Закрываем вкладку для этой задачи
            if hasattr(task, 'page_reference') and task.page_reference:
                try:
                    logger.info(f"📄 Закрываю вкладку для поставки {supply_id}")
                    await task.page_reference.close()
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка закрытия вкладки для поставки {supply_id}: {e}")
            
            # Обновляем счетчики
            await self._update_booking_counters(session_id, task)
            
            # КРИТИЧНО: Логируем финальный статус
            logger.info(f"🔚 ЗАВЕРШЕНИЕ _execute_single_booking для {supply_id}: status={task.status}, result={bool(task.result)}")
    
    async def _update_booking_counters(self, session_id: str, completed_task: BookingTask):
        """Обновляет счетчики выполненных задач."""
        if session_id not in self.active_bookings:
            return
            
        booking_info = self.active_bookings[session_id]
        
        if completed_task.status == "completed":
            booking_info["completed_tasks"] += 1
        elif completed_task.status == "failed":
            booking_info["failed_tasks"] += 1
        
        total = booking_info["total_tasks"]
        completed = booking_info["completed_tasks"]
        failed = booking_info["failed_tasks"]
        finished = completed + failed
        
        logger.info(f"📊 Прогресс {session_id}: {finished}/{total} ({completed} успешно, {failed} ошибок)")
    
    async def _finalize_booking_session(self, session_id: str):
        """Завершает сессию мультибронирования."""
        if session_id not in self.active_bookings:
            return
            
        booking_info = self.active_bookings[session_id]
        tasks = self.booking_tasks[session_id]
        
        total = booking_info["total_tasks"]
        completed = booking_info["completed_tasks"]
        failed = booking_info["failed_tasks"]
        
        booking_info["status"] = "completed"
        booking_info["end_time"] = datetime.now()
        
        # Формируем финальный отчет
        duration = (booking_info["end_time"] - booking_info["start_time"]).total_seconds()
        
        final_message = (
            f"🏁 <b>Мультибронирование завершено!</b>\n\n"
            f"📊 Всего поставок: {total}\n"
            f"✅ Успешно: {completed}\n"
            f"❌ Ошибок: {failed}\n"
            f"⏱ Время: {duration:.1f} сек\n\n"
        )
        
        # Добавляем детали об успешных бронированиях
        successful_bookings = []
        for task in tasks:
            if task.status == "completed":
                supply_name = task.supply.get("name", f"Поставка #{task.supply.get('id')}")
                successful_bookings.append(supply_name[:30])
        
        if successful_bookings:
            final_message += f"🎯 <b>Забронированы:</b>\n"
            for booking in successful_bookings:
                final_message += f"• {booking}\n"
        
        logger.info(f"🏁 Завершена сессия мультибронирования {session_id}")
        await self._notify_progress(session_id, final_message)
        
        # Очистка через некоторое время
        asyncio.create_task(self._cleanup_session(session_id, delay=300))  # 5 минут
    
    async def _notify_progress(self, session_id: str, message: str):
        """Отправляет уведомление о прогрессе."""
        if session_id in self._progress_callbacks:
            try:
                callback = self._progress_callbacks[session_id]
                await callback(message)
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления: {e}")
    
    async def _cleanup_session(self, session_id: str, delay: int = 0):
        """Очищает данные сессии."""
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Удаляем данные сессии
        self.active_bookings.pop(session_id, None)
        self.booking_tasks.pop(session_id, None)
        self._progress_callbacks.pop(session_id, None)
        
        logger.info(f"🧹 Очищена сессия мультибронирования {session_id}")
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает статус сессии мультибронирования."""
        return self.active_bookings.get(session_id)
    
    def get_active_sessions(self, user_id: int) -> List[str]:
        """Возвращает список активных сессий пользователя."""
        active_sessions = []
        for session_id, booking_info in self.active_bookings.items():
            if booking_info["user_id"] == user_id and booking_info["status"] in ["starting", "in_progress"]:
                active_sessions.append(session_id)
        return active_sessions
    
    async def cancel_session(self, session_id: str) -> bool:
        """Отменяет сессию мультибронирования."""
        if session_id not in self.active_bookings:
            return False
        
        booking_info = self.active_bookings[session_id]
        booking_info["status"] = "cancelled"
        
        # Закрываем все вкладки этой сессии
        tasks = self.booking_tasks.get(session_id, [])
        for task in tasks:
            if hasattr(task, 'page_reference') and task.page_reference and task.status == "in_progress":
                try:
                    await task.page_reference.close()
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка закрытия вкладки при отмене: {e}")
        
        await self._notify_progress(session_id, "❌ Мультибронирование отменено пользователем")
        await self._cleanup_session(session_id, delay=5)
        
        logger.info(f"❌ Отменена сессия мультибронирования {session_id}")
        return True
