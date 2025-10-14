#!/usr/bin/env python3
"""
Скрипт для полной очистки базы данных.
ВНИМАНИЕ: Удаляет ВСЕ данные из всех таблиц!
"""

import asyncio
import sys
from sqlalchemy import text

from wb_bot.app.database import init_database, close_database, get_session
from wb_bot.app.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def clear_all_tables():
    """Очистка всех таблиц в базе данных."""
    logger.warning("⚠️  ВНИМАНИЕ: Начинается очистка ВСЕХ данных из базы данных!")
    
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
            # Отключаем проверку внешних ключей (для PostgreSQL)
            logger.info("🔓 Отключаю проверку внешних ключей...")
            await session.execute(text("SET session_replication_role = 'replica';"))
            
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
                        await session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                        deleted_counts[table] = count
                        logger.info(f"   ✅ Удалено записей: {count}")
                    else:
                        logger.info(f"   ℹ️  Таблица пустая")
                        deleted_counts[table] = 0
                        
                except Exception as e:
                    logger.error(f"   ❌ Ошибка при очистке таблицы {table}: {e}")
                    # Продолжаем с другими таблицами
            
            # Включаем обратно проверку внешних ключей
            logger.info("🔒 Включаю проверку внешних ключей...")
            await session.execute(text("SET session_replication_role = 'origin';"))
            
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


async def confirm_and_clear():
    """Запрос подтверждения и очистка."""
    print("\n" + "="*60)
    print("⚠️  ВНИМАНИЕ: ОЧИСТКА БАЗЫ ДАННЫХ")
    print("="*60)
    print("Это действие удалит ВСЕ данные из базы данных:")
    print("  • Всех пользователей")
    print("  • Все API ключи")
    print("  • Все задачи мониторинга")
    print("  • Все результаты бронирования")
    print("  • Все браузерные сессии")
    print("  • Все задачи бронирования")
    print("\n⚠️  ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!\n")
    print("="*60 + "\n")
    
    # Запрашиваем подтверждение
    response = input("Введите 'DELETE ALL' для подтверждения: ")
    
    if response == "DELETE ALL":
        print("\n🚀 Начинаю очистку базы данных...\n")
        success = await clear_all_tables()
        if success:
            print("\n✅ Готово! База данных полностью очищена.\n")
            return True
        else:
            print("\n❌ Ошибка при очистке базы данных. Проверьте логи.\n")
            return False
    else:
        print("\n❌ Очистка отменена. Неверное подтверждение.\n")
        return False


async def main():
    """Главная функция."""
    success = await confirm_and_clear()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())


