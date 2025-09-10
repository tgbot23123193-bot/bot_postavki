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
    """Глобальный менеджер браузерных сессий."""
    
    def __init__(self):
        self._browser: Optional[WBBrowserAutomationPro] = None
        self._active_users: Dict[int, Any] = {}  # user_id -> session_data
        self._lock = asyncio.Lock()
    
    async def get_browser(self, user_id: int, headless: bool = True, debug_mode: bool = False) -> Optional[WBBrowserAutomationPro]:
        """Получает или создает браузер для пользователя."""
        async with self._lock:
            # Если браузер уже запущен, возвращаем его
            if self._browser and self._browser.page and not self._browser.page.is_closed():
                logger.info(f"🔄 Переиспользуем существующий браузер для пользователя {user_id}")
                self._active_users[user_id] = {
                    "headless": headless,
                    "debug_mode": debug_mode,
                    "last_used": asyncio.get_event_loop().time()
                }
                return self._browser
            
            # Создаем новый браузер
            try:
                logger.info(f"🚀 Создаю новый браузер для пользователя {user_id}")
                self._browser = WBBrowserAutomationPro(
                    headless=headless, 
                    debug_mode=debug_mode, 
                    user_id=user_id
                )
                
                logger.info(f"🔄 Запускаю браузер для пользователя {user_id}...")
                success = await self._browser.start_browser(headless=headless)
                logger.info(f"📊 Результат запуска браузера: {success}")
                
                if not success:
                    logger.error(f"❌ Не удалось запустить браузер для пользователя {user_id}")
                    self._browser = None
                    return None
                
                self._active_users[user_id] = {
                    "headless": headless,
                    "debug_mode": debug_mode,
                    "last_used": asyncio.get_event_loop().time()
                }
                
                logger.info(f"✅ Браузер успешно создан для пользователя {user_id}")
                return self._browser
                
            except Exception as e:
                logger.error(f"❌ Ошибка создания браузера для пользователя {user_id}: {e}")
                logger.error(f"❌ Тип ошибки: {type(e).__name__}")
                import traceback
                logger.error(f"❌ Трассировка: {traceback.format_exc()}")
                self._browser = None
                return None
    
    async def close_browser(self, user_id: int) -> bool:
        """Закрывает браузер для конкретного пользователя."""
        async with self._lock:
            if user_id in self._active_users:
                del self._active_users[user_id]
                logger.info(f"👤 Пользователь {user_id} отключен от браузера")
            
            # Если больше нет активных пользователей, закрываем браузер
            if not self._active_users and self._browser:
                try:
                    await self._browser.close_browser()
                    logger.info("🔒 Браузер закрыт (нет активных пользователей)")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка закрытия браузера: {e}")
                finally:
                    self._browser = None
                return True
            
            return False
    
    async def force_close_browser(self) -> None:
        """Принудительно закрывает браузер."""
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close_browser()
                    logger.info("🔒 Браузер принудительно закрыт")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка принудительного закрытия браузера: {e}")
                finally:
                    self._browser = None
                    self._active_users.clear()
    
    def is_browser_active(self) -> bool:
        """Проверяет, активен ли браузер."""
        return self._browser is not None and self._browser.page is not None and not self._browser.page.is_closed()
    
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
