#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы кнопок API ключей.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.bot.keyboards.inline import get_api_keys_list_keyboard, get_api_key_management_keyboard
from app.services.database_service import db_service
from app.database.connection import init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_api_keys_buttons(user_id: int):
    """Тестируем работу кнопок API ключей."""
    await init_database()
    
    try:
        logger.info(f"🧪 Тестирование кнопок API ключей для пользователя {user_id}")
        
        # Получаем API ключи пользователя
        api_keys = await db_service.get_user_api_keys(user_id)
        
        if not api_keys:
            logger.warning("⚠️ У пользователя нет API ключей")
            return
        
        logger.info(f"✅ Найдено {len(api_keys)} API ключей")
        
        # Тестируем клавиатуру списка ключей
        logger.info("🔧 Тестирование клавиатуры списка ключей...")
        try:
            list_keyboard = get_api_keys_list_keyboard(api_keys)
            logger.info(f"✅ Клавиатура списка создана: {len(list_keyboard.inline_keyboard)} рядов кнопок")
            
            # Проверяем кнопки
            for i, row in enumerate(list_keyboard.inline_keyboard):
                for j, button in enumerate(row):
                    logger.info(f"  Кнопка [{i}][{j}]: '{button.text}' -> '{button.callback_data}'")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания клавиатуры списка: {e}")
            import traceback
            traceback.print_exc()
        
        # Тестируем клавиатуру управления первым ключом
        logger.info("\n🔧 Тестирование клавиатуры управления ключом...")
        first_key = api_keys[0]
        
        try:
            management_keyboard = get_api_key_management_keyboard(first_key)
            logger.info(f"✅ Клавиатура управления создана: {len(management_keyboard.inline_keyboard)} рядов кнопок")
            
            # Проверяем кнопки управления
            for i, row in enumerate(management_keyboard.inline_keyboard):
                for j, button in enumerate(row):
                    logger.info(f"  Кнопка [{i}][{j}]: '{button.text}' -> '{button.callback_data}'")
                    
                    # Проверяем что кнопка удаления есть
                    if "🗑" in button.text:
                        logger.info(f"  ✅ НАЙДЕНА КНОПКА УДАЛЕНИЯ: '{button.text}'")
                        
                        # Декодируем callback_data чтобы проверить action
                        try:
                            from app.bot.keyboards.inline import APIKeyCallback
                            parsed_data = APIKeyCallback.unpack(button.callback_data)
                            logger.info(f"     Action: {parsed_data.action}")
                            logger.info(f"     Key ID: {parsed_data.key_id}")
                            
                            if parsed_data.action == "delete" and parsed_data.key_id == first_key.id:
                                logger.info(f"     ✅ Кнопка удаления настроена правильно!")
                            else:
                                logger.warning(f"     ⚠️ Неверные данные кнопки удаления")
                                
                        except Exception as e:
                            logger.error(f"     ❌ Ошибка парсинга callback_data: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания клавиатуры управления: {e}")
            import traceback
            traceback.print_exc()
        
        # Проверяем данные первого ключа
        logger.info(f"\n📊 Данные первого ключа (ID: {first_key.id}):")
        logger.info(f"  📝 Название: {first_key.name}")
        logger.info(f"  🔄 Активен: {first_key.is_active}")
        logger.info(f"  ✅ Валиден: {first_key.is_valid}")
        logger.info(f"  📈 Всего запросов: {first_key.total_requests}")
        logger.info(f"  ✅ Успешных: {first_key.successful_requests}")
        logger.info(f"  ❌ Неудачных: {first_key.failed_requests}")
        
        # Тестируем метод get_success_rate
        try:
            success_rate = first_key.get_success_rate()
            logger.info(f"  📊 Процент успеха: {success_rate * 100:.1f}%")
        except Exception as e:
            logger.error(f"  ❌ Ошибка расчета процента успеха: {e}")
        
        logger.info("\n✅ Тестирование кнопок API ключей завершено!")
        
    except Exception as e:
        logger.error(f"❌ Общая ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_database()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Укажите USER_ID")
        logger.info("💡 Пример: python test_api_keys_buttons.py 123456789")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        asyncio.run(test_api_keys_buttons(user_id))
    except ValueError:
        logger.error("❌ USER_ID должен быть числом")
        sys.exit(1)


