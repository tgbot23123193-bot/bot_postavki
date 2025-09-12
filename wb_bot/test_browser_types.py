#!/usr/bin/env python3
"""
ТЕСТ РАЗНЫХ ТИПОВ БРАУЗЕРОВ!
Chromium vs Firefox vs WebKit для обхода детекции WB.
"""

import asyncio
from app.services.browser_automation import WBBrowserAutomationPro
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_browser_type(browser_type: str, user_id: int):
    """Тестирует конкретный тип браузера."""
    logger.info(f"🚀 Запускаю {browser_type.upper()} браузер для пользователя {user_id}")
    
    browser = WBBrowserAutomationPro(
        headless=False,  # Видимые браузеры для тестирования
        debug_mode=True,
        user_id=user_id,
        browser_type=browser_type
    )
    
    try:
        # Запускаем браузер
        success = await browser.start_browser(headless=False)
        if not success:
            logger.error(f"❌ Не удалось запустить {browser_type}")
            return False
            
        logger.info(f"✅ {browser_type.upper()} браузер запущен на порту {browser.debug_port}")
        
        # Переходим на WB для проверки детекции
        await browser.page.goto("https://seller.wildberries.ru/")
        await asyncio.sleep(5)
        
        # Проверяем не заблокировал ли WB
        page_title = await browser.page.title()
        logger.info(f"📄 Заголовок страницы: {page_title}")
        
        # Делаем скриншот
        await browser.take_screenshot(f"test_{browser_type}_wb.png")
        
        # Проверяем детекцию WebDriver
        webdriver_detected = await browser.page.evaluate("""
            () => {
                return {
                    webdriver: !!window.navigator.webdriver,
                    chrome: !!window.chrome,
                    phantom: !!window.callPhantom || !!window._phantom,
                    selenium: !!window.__selenium_unwrapped || !!window.__webdriver_evaluate,
                    userAgent: window.navigator.userAgent
                }
            }
        """)
        
        logger.info(f"🔍 Детекция {browser_type}: {webdriver_detected}")
        
        # Ждем немного для визуального контроля
        await asyncio.sleep(10)
        
        logger.info(f"✅ {browser_type.upper()} тест завершен успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в {browser_type}: {e}")
        return False
    finally:
        await browser.close_browser()
        logger.info(f"🔴 {browser_type.upper()} браузер закрыт")

async def test_all_browsers():
    """Тестирует все типы браузеров."""
    browsers = [
        ("firefox", 1),
        ("webkit", 2), 
        ("chromium", 3)
    ]
    
    results = {}
    
    for browser_type, user_id in browsers:
        logger.info(f"\n{'='*50}")
        logger.info(f"ТЕСТИРУЮ {browser_type.upper()}")
        logger.info(f"{'='*50}")
        
        success = await test_browser_type(browser_type, user_id)
        results[browser_type] = success
        
        # Пауза между тестами
        await asyncio.sleep(3)
    
    # Результаты
    logger.info(f"\n{'='*50}")
    logger.info("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    logger.info(f"{'='*50}")
    
    for browser_type, success in results.items():
        status = "✅ УСПЕХ" if success else "❌ ОШИБКА"
        logger.info(f"{browser_type.upper()}: {status}")

if __name__ == "__main__":
    print("🎯 Тест разных типов браузеров для обхода детекции WB")
    print("\nБудут протестированы:")
    print("1. Firefox - рекомендуемый для WB")
    print("2. WebKit - максимальный стелс") 
    print("3. Chromium - может детектироваться")
    
    input("\nНажмите Enter для начала тестирования...")
    
    asyncio.run(test_all_browsers())

