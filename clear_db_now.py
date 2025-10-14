#!/usr/bin/env python3
"""Очистка всех таблиц в БД"""
import asyncio
import sys
from sqlalchemy import text
from wb_bot.app.database import init_database, close_database, get_session

async def clear_all():
    print("\n⚠️  ОЧИСТКА БАЗЫ ДАННЫХ\n")
    sys.stdout.flush()
    
    # Правильный список таблиц из БД (в порядке удаления с учетом FK)
    tables = [
        'balance_transactions',  # зависит от user_balances
        'payments',              # зависит от users
        'booking_results',       # зависит от monitoring_tasks
        'monitoring_tasks',      # зависит от users
        'api_keys',              # зависит от users
        'browser_sessions',      # зависит от users
        'user_balances',         # зависит от users
        'users'                  # главная таблица
    ]
    
    try:
        await init_database()
        print("✅ БД подключена\n")
        sys.stdout.flush()
        
        async with get_session() as session:
            total_deleted = 0
            
            for table in tables:
                try:
                    # Считаем записи
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    
                    if count > 0:
                        # Удаляем
                        await session.execute(text(f"DELETE FROM {table}"))
                        print(f"✅ {table:30s}: удалено {count} записей")
                        total_deleted += count
                    else:
                        print(f"ℹ️  {table:30s}: пусто")
                    sys.stdout.flush()
                    
                except Exception as e:
                    print(f"❌ {table}: {e}")
                    sys.stdout.flush()
            
            # Коммитим изменения
            await session.commit()
            
            print(f"\n{'='*60}")
            print(f"ВСЕГО УДАЛЕНО: {total_deleted} записей")
            print(f"{'='*60}\n")
            print("🎉 База данных очищена!")
            sys.stdout.flush()
            
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}\n")
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
        return False
    finally:
        await close_database()
        print("🔌 Соединение закрыто\n")
        sys.stdout.flush()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(clear_all())
    exit(0 if success else 1)



