#!/usr/bin/env python3
"""
Тестовый скрипт для проверки получения складов через WB API.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.services.wb_stocks_service import get_wb_stocks_service
from app.database.connection import init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_wb_api_stocks(user_id: int, article: str = None):
    """Тестируем получение складов через WB API."""
    await init_database()
    
    try:
        wb_stocks_service = get_wb_stocks_service()
        
        logger.info(f"🧪 Тестирование WB API для пользователя {user_id}")
        if article:
            logger.info(f"📦 Фильтрация по артикулу: {article}")
        
        # Получаем склады через API
        result = await wb_stocks_service.get_user_stocks(user_id, article)
        
        logger.info(f"📊 РЕЗУЛЬТАТ ЗАПРОСА:")
        logger.info(f"  Success: {result.get('success')}")
        logger.info(f"  User ID: {result.get('user_id')}")
        
        if result.get("success"):
            warehouses = result.get("warehouses", [])
            total_records = result.get("total_records", 0)
            
            logger.info(f"✅ УСПЕХ!")
            logger.info(f"  📈 Общих записей от API: {total_records}")
            logger.info(f"  🏪 Обработанных складов: {len(warehouses)}")
            
            if warehouses:
                logger.info(f"\n📦 СКЛАДЫ С ТОВАРАМИ:")
                for i, warehouse in enumerate(warehouses, 1):
                    name = warehouse.get('name', 'Неизвестный')
                    quantity = warehouse.get('quantity', 0)
                    quantity_full = warehouse.get('quantity_full', 0)
                    articles_count = warehouse.get('articles_count', 0)
                    
                    logger.info(f"  {i}. {name}")
                    logger.info(f"     📊 Остаток: {quantity} шт")
                    logger.info(f"     📈 Полный остаток: {quantity_full} шт")
                    logger.info(f"     📋 Артикулов: {articles_count}")
                    
                    # Показываем артикулы если их немного
                    articles = warehouse.get('articles', [])
                    if articles and len(articles) <= 3:
                        logger.info(f"     🏷️ Артикулы:")
                        for art in articles:
                            art_num = art.get('article', 'N/A')
                            art_qty = art.get('quantity', 0)
                            logger.info(f"        • {art_num} ({art_qty} шт)")
            else:
                logger.warning(f"⚠️ Склады с товарами не найдены")
                if article:
                    logger.info(f"💡 Возможные причины:")
                    logger.info(f"   • Артикул {article} отсутствует на складах")
                    logger.info(f"   • Все остатки по артикулу равны 0")
                    logger.info(f"   • Неверный формат артикула")
        else:
            error = result.get("error", "Неизвестная ошибка")
            status_code = result.get("status_code")
            
            logger.error(f"❌ ОШИБКА!")
            logger.error(f"  📝 Сообщение: {error}")
            if status_code:
                logger.error(f"  🔢 HTTP код: {status_code}")
            
            if "API ключ не найден" in error:
                logger.info(f"💡 Для исправления:")
                logger.info(f"   1. Добавьте API ключ через бота")
                logger.info(f"   2. Убедитесь что ключ активен и валиден")
                logger.info(f"   3. Проверьте права доступа ключа")
    
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
    finally:
        await close_database()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Укажите USER_ID")
        logger.info("💡 Примеры:")
        logger.info("   python test_wb_api_stocks.py 123456789")
        logger.info("   python test_wb_api_stocks.py 123456789 446796490")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        article = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(test_wb_api_stocks(user_id, article))
    except ValueError:
        logger.error("❌ USER_ID должен быть числом")
        sys.exit(1)


