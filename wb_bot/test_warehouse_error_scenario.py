#!/usr/bin/env python3
"""
Тестовый скрипт для проверки сценария ошибки при выборе склада.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.services.browser_manager import BrowserManager
from app.services.redistribution_service import get_redistribution_service
from app.database.connection import init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_warehouse_error_scenario(user_id: int, article: str):
    """Тестируем полный сценарий с ошибкой выбора склада."""
    await init_database()
    
    try:
        browser_manager = BrowserManager()
        redistribution_service = get_redistribution_service(browser_manager, fast_mode=False)
        
        logger.info(f"🚀 Запуск браузера для пользователя {user_id}...")
        browser = await browser_manager.get_browser(user_id, headless=False, debug_mode=True)
        if not browser:
            logger.error("❌ Не удалось запустить браузер")
            return
        
        # Шаг 1: Открытие страницы
        logger.info("📄 Шаг 1: Открытие страницы перераспределения...")
        result = await redistribution_service.open_redistribution_page(user_id)
        if not result["success"]:
            logger.error(f"❌ Ошибка открытия страницы: {result['error']}")
            return
        logger.info("✅ Страница открыта")
        
        # Шаг 2: Ввод артикула и выбор товара
        logger.info(f"📝 Шаг 2: Ввод артикула {article}...")
        result = await redistribution_service.click_redistribution_menu_and_fill_article(user_id, article)
        if not result["success"]:
            logger.error(f"❌ Ошибка ввода артикула: {result['error']}")
            return
        logger.info("✅ Артикул введен и товар выбран")
        
        # Шаг 3: Получение списка складов
        logger.info("🏪 Шаг 3: Получение списка складов...")
        result = await redistribution_service.get_available_warehouses(user_id)
        if not result["success"]:
            logger.error(f"❌ Ошибка получения складов: {result['error']}")
            return
        
        warehouses = result["warehouses"]
        logger.info(f"✅ Получено {len(warehouses)} складов")
        for i, wh in enumerate(warehouses, 1):
            logger.info(f"  {i}. {wh['name']} (ID: {wh['id']})")
        
        if not warehouses:
            logger.error("❌ Нет доступных складов")
            return
        
        # Шаг 4: Пытаемся выбрать каждый склад и смотрим на ошибки
        for i, warehouse in enumerate(warehouses):
            logger.info(f"🎯 Шаг 4.{i+1}: Пробуем выбрать склад '{warehouse['name']}'...")
            
            result = await redistribution_service.select_warehouse(user_id, warehouse)
            
            logger.info(f"📋 РЕЗУЛЬТАТ ВЫБОРА СКЛАДА '{warehouse['name']}':")
            logger.info(f"  success: {result.get('success')}")
            logger.info(f"  error: {result.get('error')}")
            logger.info(f"  need_retry: {result.get('need_retry')}")
            logger.info(f"  error_messages: {result.get('error_messages')}")
            
            if result.get("success"):
                logger.info(f"✅ Склад '{warehouse['name']}' выбран успешно!")
                break
            elif result.get("need_retry") and result.get("error_messages"):
                logger.warning(f"⚠️ Ошибка выбора склада '{warehouse['name']}':")
                for j, msg in enumerate(result.get("error_messages", []), 1):
                    logger.warning(f"    {j}. {msg}")
                logger.info("🔄 Попробуем следующий склад...")
            else:
                logger.error(f"❌ Неожиданная ошибка при выборе склада '{warehouse['name']}': {result.get('error')}")
        
        # Оставляем браузер открытым
        logger.info("🖥️ Тест завершен. Браузер оставлен открытым. Нажмите Ctrl+C для завершения.")
        while True:
            await asyncio.sleep(60)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Тест прерван пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}")
    finally:
        await close_database()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        logger.error("❌ Укажите USER_ID и ARTICLE")
        logger.info("💡 Пример: python test_warehouse_error_scenario.py 123456789 446796490")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        article = sys.argv[2]
        asyncio.run(test_warehouse_error_scenario(user_id, article))
    except ValueError:
        logger.error("❌ USER_ID должен быть числом")
        sys.exit(1)


