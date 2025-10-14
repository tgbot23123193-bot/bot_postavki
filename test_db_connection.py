#!/usr/bin/env python3
"""
Тест подключения к базе данных PostgreSQL.
"""

import asyncio
from wb_bot.app.database import init_database, health_check, close_database


async def test_database_connection():
    """Тестирование подключения к базе данных."""
    print("🔌 Тестирую подключение к базе данных...")
    
    try:
        # Инициализируем подключение
        await init_database()
        print("✅ База данных инициализирована")
        
        # Проверяем здоровье БД
        is_healthy = await health_check()
        if is_healthy:
            print("✅ База данных доступна и работает")
        else:
            print("❌ База данных недоступна")
            return False
        
        print("🎉 Тест подключения к БД успешен!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False
    finally:
        # Закрываем подключение
        await close_database()
        print("🔌 Подключение к БД закрыто")


if __name__ == "__main__":
    success = asyncio.run(test_database_connection())
    exit(0 if success else 1)
