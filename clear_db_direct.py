#!/usr/bin/env python3
"""Прямая очистка БД"""
import asyncio
import sys
from sqlalchemy import text
from wb_bot.app.database import init_database, close_database, get_session

async def clear():
    print("Начинаю очистку БД...")
    sys.stdout.flush()
    
    tables = ['booking_results', 'booking_tasks', 'monitoring_tasks', 'api_keys', 'browser_sessions', 'users']
    
    try:
        await init_database()
        print("БД инициализирована")
        sys.stdout.flush()
        
        async with get_session() as session:
            for table in tables:
                try:
                    # Считаем записи
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"{table}: {count} записей")
                    sys.stdout.flush()
                    
                    # Удаляем
                    if count > 0:
                        await session.execute(text(f"DELETE FROM {table}"))
                        print(f"  -> удалено {count} записей")
                        sys.stdout.flush()
                except Exception as e:
                    print(f"Ошибка в {table}: {e}")
                    sys.stdout.flush()
            
            await session.commit()
            print("\n✅ БД очищена!")
            sys.stdout.flush()
            
    except Exception as e:
        print(f"ОШИБКА: {e}")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        return False
    finally:
        await close_database()
    
    return True

if __name__ == "__main__":
    asyncio.run(clear())



