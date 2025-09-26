#!/usr/bin/env python3
"""
Скрипт для запуска браузера конкретного пользователя без бота.
Использование: python launch_browser.py USER_ID
"""

import sys
import asyncio
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.services.browser_manager import BrowserManager
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)

async def launch_user_browser(user_id: int):
    """Запускает браузер для конкретного пользователя."""
    try:
        logger.info(f"🚀 Запуск браузера для пользователя {user_id}")
        
        # Получаем настройки
        settings = get_settings()
        
        # Создаем браузер менеджер
        browser_manager = BrowserManager()
        
        # Запускаем браузер в НЕ headless режиме
        browser = await browser_manager.get_browser(
            user_id=user_id,
            headless=False,  # Видимый браузер
            debug_mode=True  # Режим отладки
        )
        
        if not browser:
            logger.error(f"❌ Не удалось запустить браузер для пользователя {user_id}")
            return
        
        logger.info(f"✅ Браузер запущен для пользователя {user_id}")
        logger.info(f"📂 Профиль: {browser.user_data_dir}")
        logger.info(f"🌐 Страница: {browser.page.url if browser.page else 'Не загружена'}")
        
        print(f"\n🎯 Браузер пользователя {user_id} запущен!")
        print(f"📂 Профиль: {browser.user_data_dir}")
        
        if browser.page:
            print(f"🌐 Текущая страница: {browser.page.url}")
        
        print("\n💡 Доступные команды:")
        print("  - Браузер будет работать до закрытия этого скрипта")
        print("  - Нажмите Ctrl+C для завершения")
        print("  - Все действия в браузере сохранятся в профиле пользователя")
        
        # Ждем завершения (Ctrl+C)
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал завершения")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске браузера: {e}")
    finally:
        # Закрываем браузер менеджер
        if 'browser_manager' in locals():
            await browser_manager.close_all()
            logger.info("🔒 Все браузеры закрыты")

def main():
    """Главная функция."""
    if len(sys.argv) != 2:
        print("❌ Ошибка: Неверные аргументы")
        print("\n📋 Использование:")
        print("  python launch_browser.py USER_ID")
        print("\n💡 Примеры:")
        print("  python launch_browser.py 123456789")
        print("  python launch_browser.py 5123262366")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print("❌ Ошибка: USER_ID должен быть числом")
        print("\n💡 Пример: python launch_browser.py 123456789")
        sys.exit(1)
    
    print(f"🚀 Запуск браузера для пользователя {user_id}...")
    
    # Запускаем асинхронную функцию
    asyncio.run(launch_user_browser(user_id))

if __name__ == "__main__":
    main()


