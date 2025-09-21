#!/usr/bin/env python3
"""
Тест исправления ошибки 'NoneType' object has no attribute 'is_closed'
"""
import asyncio
import logging
from .app.services.browser_manager import browser_manager

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def test_browser_fix():
    """Тестирует исправление ошибки с None."""
    
    try:
        print("🚀 Тестируем исправление ошибки 'NoneType' object has no attribute 'is_closed'...")
        
        # Тестируем получение браузера
        print("\n🔍 Тестируем получение браузера...")
        browser = await browser_manager.get_browser(999999999, headless=True, debug_mode=False)
        
        if browser:
            print("✅ Браузер получен успешно")
            
            # Проверяем наличие page
            if browser.page:
                print("✅ Страница браузера инициализирована")
                
                # Проверяем is_closed
                try:
                    is_closed = browser.page.is_closed()
                    print(f"✅ is_closed() работает: {is_closed}")
                except Exception as e:
                    print(f"❌ Ошибка is_closed(): {e}")
            else:
                print("❌ Страница браузера не инициализирована")
            
            # Проверяем is_browser_active
            try:
                is_active = browser_manager.is_browser_active()
                print(f"✅ is_browser_active() работает: {is_active}")
            except Exception as e:
                print(f"❌ Ошибка is_browser_active(): {e}")
            
        else:
            print("❌ Не удалось получить браузер")
        
        # Закрываем браузер
        print("\n🔒 Закрываем браузер...")
        closed = await browser_manager.close_browser(999999999)
        print(f"Браузер закрыт: {closed}")
        
        print("\n✅ Тест завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка во время теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_browser_fix())


