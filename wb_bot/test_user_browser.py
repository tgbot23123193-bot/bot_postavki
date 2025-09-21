#!/usr/bin/env python3
"""
Тест запуска браузера для конкретного пользователя
"""
import asyncio
import sys
from app.services.browser_manager import BrowserManager
from app.services.browser_automation import WBBrowserAutomationPro
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_user_browser(user_id: int):
    """Запускает браузер для конкретного пользователя."""
    print(f"🚀 Запуск браузера для пользователя {user_id}")
    
    try:
        # Создаем менеджер браузеров
        browser_manager = BrowserManager()
        
        # Запускаем браузер для пользователя
        browser = await browser_manager.get_browser(
            user_id=user_id,
            headless=False,  # С видимым окном
            debug_mode=True,  # Режим отладки
            browser_type="firefox"  # Используем Firefox
        )
        
        if browser and browser.page:
            print(f"✅ Браузер успешно запущен для пользователя {user_id}")
            print(f"🔗 Debug порт: {browser.debug_port}")
            print(f"📁 User data: {browser.user_data_dir}")
            print(f"🍪 Cookies файл: {browser.cookies_file}")
            
            # Переходим на страницу WB
            await browser.page.goto("https://seller.wildberries.ru")
            print(f"🌐 Открыта страница WB")
            
            print(f"🔥 Браузер работает! Нажмите Ctrl+C для закрытия...")
            
            # Ждем бесконечно пока пользователь не закроет
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print(f"\n👋 Закрываю браузер пользователя {user_id}...")
                await browser.close_browser()
                print(f"✅ Браузер закрыт!")
        else:
            print(f"❌ Не удалось запустить браузер для пользователя {user_id}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Ошибка запуска браузера для пользователя {user_id}: {e}")

async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("❌ Укажите USER_ID!")
        print("Использование: python test_user_browser.py <USER_ID>")
        print("Пример: python test_user_browser.py 5123262366")
        return
    
    try:
        user_id = int(sys.argv[1])
        print(f"🎯 Целевой пользователь: {user_id}")
        
        # Проверяем что ID начинается на 5
        if not str(user_id).startswith('5'):
            print(f"⚠️ USER_ID {user_id} не начинается на 5, но запускаем...")
        
        await test_user_browser(user_id)
        
    except ValueError:
        print(f"❌ Неверный формат USER_ID: {sys.argv[1]}")
        print("USER_ID должен быть числом!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())


