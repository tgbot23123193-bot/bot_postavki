#!/usr/bin/env python3
"""
Тестовый скрипт для проверки управления API ключами.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.services.database_service import db_service
from app.database.connection import init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_api_key_management(user_id: int):
    """Тестируем управление API ключами."""
    await init_database()
    
    try:
        logger.info(f"🧪 Тестирование управления API ключами для пользователя {user_id}")
        
        # 1. Получаем список существующих ключей
        logger.info("📋 Шаг 1: Получение списка API ключей...")
        existing_keys = await db_service.get_user_api_keys(user_id)
        
        logger.info(f"✅ Найдено {len(existing_keys)} API ключей:")
        for i, key in enumerate(existing_keys, 1):
            status = "✅ Активен" if key.is_active else "❌ Неактивен"
            valid = "✅ Валиден" if key.is_valid else "❌ Не валиден"
            logger.info(f"  {i}. ID: {key.id}")
            logger.info(f"     📝 Название: {key.name or 'Без названия'}")
            logger.info(f"     📅 Создан: {key.created_at.strftime('%d.%m.%Y %H:%M')}")
            logger.info(f"     🔄 Статус: {status}")
            logger.info(f"     ✅ Валидность: {valid}")
            logger.info(f"     📊 Использований: {key.total_requests or 0}")
            if key.last_used:
                logger.info(f"     🕐 Последнее использование: {key.last_used.strftime('%d.%m.%Y %H:%M')}")
            else:
                logger.info(f"     🕐 Последнее использование: Никогда")
        
        if not existing_keys:
            logger.warning("⚠️ У пользователя нет API ключей")
            logger.info("💡 Для тестирования удаления нужно сначала добавить API ключ через бота")
            return
        
        # 2. Тестируем получение конкретного ключа
        logger.info(f"\n🔍 Шаг 2: Тестирование получения конкретного ключа...")
        first_key = existing_keys[0]
        retrieved_key = await db_service.get_api_key_by_id(first_key.id, user_id)
        
        if retrieved_key:
            logger.info(f"✅ Ключ {first_key.id} успешно получен")
            logger.info(f"   📝 Название: {retrieved_key.name}")
            logger.info(f"   🔄 Статус: {'Активен' if retrieved_key.is_active else 'Неактивен'}")
        else:
            logger.error(f"❌ Не удалось получить ключ {first_key.id}")
        
        # 3. Тестируем безопасность (пытаемся получить ключ другого пользователя)
        logger.info(f"\n🔒 Шаг 3: Тестирование безопасности...")
        fake_user_id = user_id + 999999  # Несуществующий пользователь
        security_test = await db_service.get_api_key_by_id(first_key.id, fake_user_id)
        
        if security_test is None:
            logger.info("✅ Система безопасности работает: ключ другого пользователя недоступен")
        else:
            logger.error("❌ ОШИБКА БЕЗОПАСНОСТИ: Получен доступ к чужому ключу!")
        
        # 4. Показываем симуляцию удаления (без реального удаления)
        logger.info(f"\n🗑️ Шаг 4: Симуляция удаления ключа {first_key.id}...")
        logger.info(f"⚠️ Для безопасности реальное удаление НЕ выполняется")
        logger.info(f"📋 Информация о ключе для удаления:")
        logger.info(f"   📝 Название: {first_key.name or 'Без названия'}")
        logger.info(f"   📅 Создан: {first_key.created_at.strftime('%d.%m.%Y %H:%M')}")
        logger.info(f"   🔄 Статус: {'✅ Активен' if first_key.is_active else '❌ Неактивен'}")
        logger.info(f"   📊 Использований: {first_key.total_requests or 0}")
        
        # Если пользователь хочет протестировать реальное удаление
        if len(sys.argv) > 2 and sys.argv[2].lower() == "delete_real":
            logger.warning(f"⚠️ ВНИМАНИЕ: Запрошено реальное удаление ключа {first_key.id}")
            
            # Подтверждение
            confirmation = input(f"Введите 'DELETE {first_key.id}' для подтверждения удаления: ")
            if confirmation == f"DELETE {first_key.id}":
                logger.info(f"🗑️ Удаляем ключ {first_key.id}...")
                success = await db_service.delete_api_key(first_key.id, user_id)
                
                if success:
                    logger.info(f"✅ Ключ {first_key.id} успешно удален")
                    
                    # Проверяем что ключ действительно удален
                    deleted_check = await db_service.get_api_key_by_id(first_key.id, user_id)
                    if deleted_check is None:
                        logger.info("✅ Подтверждено: ключ удален из базы данных")
                    else:
                        logger.error("❌ ОШИБКА: ключ все еще в базе данных!")
                    
                    # Показываем обновленный список
                    updated_keys = await db_service.get_user_api_keys(user_id)
                    logger.info(f"📋 Обновленный список: {len(updated_keys)} ключей")
                else:
                    logger.error(f"❌ Не удалось удалить ключ {first_key.id}")
            else:
                logger.info("❌ Удаление отменено (неверное подтверждение)")
        else:
            logger.info("💡 Для реального удаления добавьте параметр 'delete_real'")
            logger.info(f"   Пример: python test_api_key_management.py {user_id} delete_real")
        
        logger.info("\n✅ Тестирование управления API ключами завершено!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
    finally:
        await close_database()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Укажите USER_ID")
        logger.info("💡 Примеры:")
        logger.info("   python test_api_key_management.py 123456789")
        logger.info("   python test_api_key_management.py 123456789 delete_real")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        asyncio.run(test_api_key_management(user_id))
    except ValueError:
        logger.error("❌ USER_ID должен быть числом")
        sys.exit(1)


