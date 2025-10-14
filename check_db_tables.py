#!/usr/bin/env python3
"""Проверка таблиц в БД"""
import asyncio
import sys
from sqlalchemy import text
from wb_bot.app.database import init_database, close_database, get_session

async def check_tables():
    print("Проверяю таблицы в БД...")
    sys.stdout.flush()
    
    try:
        await init_database()
        print("БД инициализирована\n")
        sys.stdout.flush()
        
        async with get_session() as session:
            # Получаем список всех таблиц
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result]
            
            print(f"Найдено таблиц: {len(tables)}\n")
            sys.stdout.flush()
            
            if tables:
                print("Список таблиц:")
                for table in tables:
                    # Считаем записи в каждой таблице
                    count_result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    print(f"  - {table:30s}: {count:6d} записей")
                    sys.stdout.flush()
            else:
                print("❌ Таблиц не найдено! База данных пустая.")
                print("Нужно применить миграции: cd wb_bot && alembic upgrade head")
                sys.stdout.flush()
            
    except Exception as e:
        print(f"ОШИБКА: {e}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(check_tables())



