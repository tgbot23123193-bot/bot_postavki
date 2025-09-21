#!/usr/bin/env python3
"""
ЁБАНЫЙ ТЕСТ МУЛЬТИБРАУЗЕРА!
Запускает 2-5 браузеров одновременно без конфликтов.
"""

import asyncio
import time
from .app.services.browser_automation import WBBrowserAutomationPro
from .app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_browser(user_id: int, url: str = "https://www.google.com"):
    """Тестирует один браузер с указанным user_id."""
    logger.info(f"🚀 Запускаю браузер {user_id}...")
    
    browser = WBBrowserAutomationPro(
        headless=False,  # Видимые браузеры для тестирования
        debug_mode=True,
        user_id=user_id
    )
    
    try:
        # Инициализация браузера
        await browser.start_browser(headless=False)
        logger.info(f"✅ Браузер {user_id} запущен на порту {browser.debug_port}")
        
        # Переходим на тестовую страницу
        await browser.page.goto(url)
        await asyncio.sleep(3)
        
        # Делаем скриншот
        await browser.take_screenshot(f"test_browser_{user_id}.png")
        
        # Дополнительные действия для тестирования
        await browser.page.fill('input[name="q"]', f"Тест браузера {user_id}")
        await asyncio.sleep(2)
        
        # Еще один скриншот
        await browser.take_screenshot(f"test_browser_{user_id}_search.png")
        
        logger.info(f"✅ Браузер {user_id} успешно отработал!")
        
        # Держим браузер открытым для визуального контроля
        await asyncio.sleep(10)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в браузере {user_id}: {e}")
    finally:
        await browser.close_browser()
        logger.info(f"🔴 Браузер {user_id} закрыт")

async def test_multiple_browsers():
    """Тестирует несколько браузеров одновременно."""
    logger.info("🎯 НАЧИНАЮ ТЕСТ МУЛЬТИБРАУЗЕРА!")
    
    # Создаем задачи для 3 браузеров одновременно
    tasks = []
    for i in range(1, 4):  # Браузеры с user_id 1, 2, 3
        task = asyncio.create_task(test_browser(i))
        tasks.append(task)
        
        # Небольшая задержка между запусками
        await asyncio.sleep(2)
    
    # Ждем завершения всех браузеров
    logger.info("⏳ Жду завершения всех браузеров...")
    await asyncio.gather(*tasks)
    
    logger.info("🎉 ТЕСТ МУЛЬТИБРАУЗЕРА ЗАВЕРШЕН!")

async def test_single_browser():
    """Тестирует один браузер без user_id (как раньше)."""
    logger.info("🔍 Тестирую обычный браузер без user_id...")
    
    browser = WBBrowserAutomationPro(headless=False, debug_mode=True)
    
    try:
        await browser.start_browser(headless=False)
        logger.info(f"✅ Обычный браузер запущен на порту {browser.debug_port}")
        
        await browser.page.goto("https://www.google.com")
        await asyncio.sleep(3)
        
        await browser.take_screenshot("test_single_browser.png")
        
        await asyncio.sleep(5)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в обычном браузере: {e}")
    finally:
        await browser.close_browser()

if __name__ == "__main__":
    print("🎯 Выберите тест:")
    print("1. Одиночный браузер (как раньше)")
    print("2. Мультибраузер (3 браузера одновременно)")
    
    choice = input("Введите номер (1 или 2): ").strip()
    
    if choice == "1":
        asyncio.run(test_single_browser())
    elif choice == "2":
        asyncio.run(test_multiple_browsers())
    else:
        print("❌ Неверный выбор!")
