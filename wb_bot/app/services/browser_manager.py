"""
Глобальный менеджер браузерных сессий.
Управляет единой сессией браузера для всех функций бота.
"""
import asyncio
from typing import Optional, Dict, Any
from .browser_automation import WBBrowserAutomationPro
from ..utils.logger import get_logger

logger = get_logger(__name__)

class BrowserManager:
    """МУЛЬТИБРАУЗЕРНЫЙ менеджер сессий - КАЖДЫЙ ПОЛЬЗОВАТЕЛЬ = ОТДЕЛЬНЫЙ БРАУЗЕР!"""
    
    def __init__(self):
        # КРИТИЧНО: СЛОВАРЬ БРАУЗЕРОВ! Каждый user_id = отдельный браузер
        self._browsers: Dict[int, WBBrowserAutomationPro] = {}  # user_id -> browser_instance
        self._active_users: Dict[int, Any] = {}  # user_id -> session_data
        self._lock = asyncio.Lock()
    
    async def get_browser(self, user_id: int, headless: bool = True, debug_mode: bool = False, browser_type: str = "firefox") -> Optional[WBBrowserAutomationPro]:
        """ПОЛУЧАЕТ ИЛИ СОЗДАЕТ ОТДЕЛЬНЫЙ БРАУЗЕР ДЛЯ КАЖДОГО ПОЛЬЗОВАТЕЛЯ!"""
        async with self._lock:
            # ПРОВЕРЯЕМ: есть ли уже браузер для ЭТОГО пользователя
            if user_id in self._browsers:
                browser = self._browsers[user_id]
                if browser and browser.page and not browser.page.is_closed():
                    logger.info(f"🔄 Переиспользуем браузер пользователя {user_id} (порт {browser.debug_port})")
                    self._active_users[user_id] = {
                        "headless": headless,
                        "debug_mode": debug_mode,
                        "last_used": asyncio.get_event_loop().time()
                    }
                    return browser
                else:
                    # Браузер умер - удаляем из словаря
                    logger.warning(f"⚠️ Браузер пользователя {user_id} не активен, создаю новый")
                    del self._browsers[user_id]
            
            # СОЗДАЕМ НОВЫЙ БРАУЗЕР ДЛЯ ЭТОГО ПОЛЬЗОВАТЕЛЯ
            try:
                logger.info(f"🚀 НОВЫЙ БРАУЗЕР для пользователя {user_id} (тип: {browser_type}, headless: {headless})")
                browser = WBBrowserAutomationPro(
                    headless=headless, 
                    debug_mode=debug_mode, 
                    user_id=user_id,
                    browser_type=browser_type  # ПЕРЕДАЕМ ТИП БРАУЗЕРА!
                )
                
                logger.info(f"🔄 Запускаю браузер для пользователя {user_id}...")
                success = await browser.start_browser(headless=headless)
                logger.info(f"📊 Результат запуска браузера: {success}")
                
                if not success:
                    logger.error(f"❌ Не удалось запустить браузер для пользователя {user_id}")
                    return None
                
                # СОХРАНЯЕМ в словарь браузеров
                self._browsers[user_id] = browser
                self._active_users[user_id] = {
                    "headless": headless,
                    "debug_mode": debug_mode,
                    "last_used": asyncio.get_event_loop().time()
                }
                
                logger.info(f"✅ Браузер успешно создан для пользователя {user_id} (порт {browser.debug_port})")
                return browser
                
            except Exception as e:
                logger.error(f"❌ Ошибка создания браузера для пользователя {user_id}: {e}")
                logger.error(f"❌ Тип ошибки: {type(e).__name__}")
                import traceback
                logger.error(f"❌ Трассировка: {traceback.format_exc()}")
                return None
    
    async def close_browser(self, user_id: int) -> bool:
        """ЗАКРЫВАЕТ БРАУЗЕР КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ."""
        async with self._lock:
            # Удаляем пользователя из активных
            if user_id in self._active_users:
                del self._active_users[user_id]
                logger.info(f"👤 Пользователь {user_id} отключен от браузера")
            
            # ЗАКРЫВАЕМ БРАУЗЕР ЭТОГО ПОЛЬЗОВАТЕЛЯ
            if user_id in self._browsers:
                browser = self._browsers[user_id]
                try:
                    await browser.close_browser()
                    logger.info(f"🔒 Браузер пользователя {user_id} закрыт")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка закрытия браузера пользователя {user_id}: {e}")
                finally:
                    del self._browsers[user_id]
                return True
            
            return False
    
    async def create_session_clone(self, source_user_id: int, target_user_id: int, browser_type: str = "firefox") -> Optional[WBBrowserAutomationPro]:
        """
        Создает клон браузера с той же сессией для мультибронирования.
        
        Args:
            source_user_id: ID исходного пользователя (источник сессии)
            target_user_id: ID целевого пользователя (новый браузер)
            browser_type: Тип браузера
            
        Returns:
            Новый браузер с скопированной сессией или None
        """
        logger.info(f"🎭 Создаю клон сессии: {source_user_id} -> {target_user_id}")
        
        # Проверяем что исходный браузер существует
        source_browser = self._browsers.get(source_user_id)
        if not source_browser:
            logger.error(f"❌ Исходный браузер пользователя {source_user_id} не найден")
            return None
        
        try:
            # Создаем новый браузер для целевого пользователя
            target_browser = await self.get_browser(
                user_id=target_user_id, 
                headless=True, 
                debug_mode=False, 
                browser_type=browser_type
            )
            
            if not target_browser:
                logger.error(f"❌ Не удалось создать целевой браузер для {target_user_id}")
                return None
            
            # Копируем cookies и сессию
            await self._copy_browser_session(source_browser, target_browser)
            
            logger.info(f"✅ Сессия успешно скопирована: {source_user_id} -> {target_user_id}")
            return target_browser
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания клона сессии: {e}")
            return None
    
    async def _copy_browser_session(self, source_browser: WBBrowserAutomationPro, target_browser: WBBrowserAutomationPro):
        """Копирует сессию между браузерами (только cookies для безопасности)."""
        try:
            # Получаем cookies из исходного браузера
            logger.info("🍪 Копирую cookies...")
            source_cookies = await source_browser.page.context.cookies()
            
            if source_cookies:
                # Устанавливаем cookies в целевой браузер
                await target_browser.page.context.add_cookies(source_cookies)
                logger.info(f"✅ Скопировано {len(source_cookies)} cookies")
            else:
                logger.warning("⚠️ В исходном браузере нет cookies для копирования")
            
            # Переходим на главную страницу WB в целевом браузере для активации cookies
            logger.info("🌐 Активирую cookies на главной странице WB...")
            await target_browser.page.goto("https://suppliers.wildberries.ru", wait_until="domcontentloaded")
            
            # Даём время на загрузку и применение cookies
            await asyncio.sleep(2)
            
            logger.info("✅ Сессия успешно скопирована (cookies)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка копирования сессии: {e}")
            raise
    
    async def force_close_browser(self) -> None:
        """ПРИНУДИТЕЛЬНО ЗАКРЫВАЕТ ВСЕ БРАУЗЕРЫ."""
        async with self._lock:
            # ЗАКРЫВАЕМ ВСЕ БРАУЗЕРЫ
            for user_id, browser in self._browsers.items():
                try:
                    await browser.close_browser()
                    logger.info(f"🔒 Браузер пользователя {user_id} принудительно закрыт")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка принудительного закрытия браузера {user_id}: {e}")
            
            # ОЧИЩАЕМ ВСЕ СЛОВАРИ
            self._browsers.clear()
            self._active_users.clear()
    
    def is_browser_active(self, user_id: int = None) -> bool:
        """ПРОВЕРЯЕТ АКТИВНОСТЬ БРАУЗЕРА КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ ИЛИ ЛЮБОГО."""
        if user_id:
            # Проверяем браузер конкретного пользователя
            browser = self._browsers.get(user_id)
            return browser is not None and browser.page is not None and not browser.page.is_closed()
        else:
            # Проверяем есть ли хотя бы один активный браузер
            return len(self._browsers) > 0
    
    def get_active_users(self) -> list:
        """Возвращает список активных пользователей."""
        return list(self._active_users.keys())
    
    async def cleanup_inactive_users(self, timeout: int = 300) -> None:
        """Очищает неактивных пользователей (по умолчанию 5 минут)."""
        current_time = asyncio.get_event_loop().time()
        inactive_users = []
        
        for user_id, data in self._active_users.items():
            if current_time - data["last_used"] > timeout:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            await self.close_browser(user_id)
            logger.info(f"🧹 Пользователь {user_id} удален за неактивность")

# Глобальный экземпляр менеджера
browser_manager = BrowserManager()
