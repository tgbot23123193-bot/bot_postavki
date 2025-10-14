#!/usr/bin/env python3
"""
Принудительная очистка базы данных без подтверждения.
"""

import asyncio
from sqlalchemy import text

from wb_bot.app.database import init_database, close_database, get_session
from wb_bot.app.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def force_clear_database():
    """Принудительная очистка всех таблиц."""
    logger.info("🗑️  ПРИНУДИТЕЛЬНАЯ ОЧИСТКА БАЗЫ ДАННЫХ")
    
    # Список таблиц в порядке удаления (с учетом внешних ключей)
    tables = [
        'booking_results',
        'booking_tasks', 
        'monitoring_tasks',
        'api_keys',
        'browser_sessions',
        'users'
    ]
    
    try:
        # Инициализируем базу данных
        await init_database()
        logger.info("✅ База данных инициализирована")
        
        async with get_session() as session:
            deleted_counts = {}
            
            # Удаляем данные из каждой таблицы
            for table in tables:
                try:
                    logger.info(f"🗑️  Очищаю таблицу: {table}")
                    
                    # Подсчитываем количество записей перед удалением
                    count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    
                    if count > 0:
                        # Удаляем все записи
                        await session.execute(text(f"DELETE FROM {table}"))
                        deleted_counts[table] = count
                        logger.info(f"   ✅ Удалено записей: {count}")
                    else:
                        logger.info(f"   ℹ️  Таблица пустая")
                        deleted_counts[table] = 0
                        
                except Exception as e:
                    logger.error(f"   ❌ Ошибка при очистке таблицы {table}: {e}")
                    # Продолжаем с другими таблицами
            
            # Сохраняем изменения
            await session.commit()
            
            # Выводим итоговую статистику
            logger.info("\n" + "="*60)
            logger.info("📊 СТАТИСТИКА ОЧИСТКИ:")
            logger.info("="*60)
            total_deleted = 0
            for table, count in deleted_counts.items():
                logger.info(f"   {table:30s}: {count:6d} записей")
                total_deleted += count
            logger.info("="*60)
            logger.info(f"   {'ВСЕГО УДАЛЕНО':30s}: {total_deleted:6d} записей")
            logger.info("="*60 + "\n")
            
            logger.info("✅ База данных успешно очищена!")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при очистке базы данных: {e}")
        import traceback
        logger.error(f"Трассировка:\n{traceback.format_exc()}")
        return False
    finally:
        # Закрываем соединение с базой данных
        await close_database()
        logger.info("🔌 Соединение с базой данных закрыто")
    
    return True


if __name__ == "__main__":
    print("\n⚠️  ПРИНУДИТЕЛЬНАЯ ОЧИСТКА БАЗЫ ДАННЫХ БЕЗ ПОДТВЕРЖДЕНИЯ!\n")
    success = asyncio.run(force_clear_database())
    exit(0 if success else 1)



