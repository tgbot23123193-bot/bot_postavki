#!/usr/bin/env python3
"""
Тест для проверки исправления кнопок API ключей.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.bot.handlers.api_keys import list_api_keys, manage_api_key
from app.bot.keyboards.inline import APIKeyCallback
from app.database.connection import init_database, close_database
from app.utils.logger import get_logger
from unittest.mock import AsyncMock, MagicMock

logger = get_logger(__name__)

async def test_api_buttons_fix():
    """Тестируем исправленные кнопки API ключей."""
    await init_database()
    
    try:
        logger.info("🧪 Тестирование исправленных кнопок API ключей")
        
        # Создаем мокированный callback
        mock_callback = AsyncMock()
        mock_callback.from_user.id = 5123262366
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        
        # Тестируем обработчик list
        logger.info("\n📋 Тестирование обработчика 'list'...")
        await list_api_keys(mock_callback)
        
        # Проверяем что edit_text был вызван
        if mock_callback.message.edit_text.called:
            call_args = mock_callback.message.edit_text.call_args
            text = call_args[0][0] if call_args[0] else "No text"
            logger.info(f"✅ edit_text вызван с текстом: {text[:200]}...")
            
            if "reply_markup" in call_args[1]:
                logger.info("✅ reply_markup передан в edit_text")
            else:
                logger.error("❌ reply_markup НЕ передан в edit_text")
        else:
            logger.error("❌ edit_text НЕ был вызван")
        
        # Тестируем обработчик manage
        logger.info("\n🔧 Тестирование обработчика 'manage'...")
        
        # Создаем callback_data для manage
        callback_data = APIKeyCallback(action="manage", key_id=1)
        
        await manage_api_key(mock_callback, callback_data)
        
        # Проверяем что answer был вызван с сообщением загрузки
        if mock_callback.answer.called:
            answer_calls = mock_callback.answer.call_args_list
            logger.info(f"✅ callback.answer вызван {len(answer_calls)} раз(а)")
            for i, call in enumerate(answer_calls):
                args = call[0] if call[0] else []
                message = args[0] if args else "No message"
                logger.info(f"  Call {i+1}: '{message}'")
        else:
            logger.error("❌ callback.answer НЕ был вызван")
        
        logger.info("\n✅ Тестирование завершено!")
        logger.info("\n🔄 ПОПРОБУЙТЕ ТЕПЕРЬ В БОТЕ:")
        logger.info("1. Перезапустите бота")
        logger.info("2. Главное меню → 🔑 API ключи → 📋 Мои ключи")
        logger.info("3. Нажмите на ключ")
        logger.info("4. Должна появиться кнопка '🗑 Удалить'")
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(test_api_buttons_fix())


