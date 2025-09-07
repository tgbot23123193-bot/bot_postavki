#!/usr/bin/env python3
"""
Простой тест бота для проверки работоспособности.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота
BOT_TOKEN = "8297598368:AAFAjtygKnsIwocwbdC4qTr-lmEFRZ8k4qA"

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer("🎉 Привет! Бот работает!")
    print(f"Получена команда /start от пользователя {message.from_user.id}")

@dp.message(Command("test"))
async def cmd_test(message: Message):
    """Обработчик команды /test"""
    await message.answer("✅ Тест прошел успешно!")
    print(f"Получена команда /test от пользователя {message.from_user.id}")

@dp.message()
async def echo_handler(message: Message):
    """Эхо-обработчик для всех сообщений"""
    await message.answer(f"Получено сообщение: {message.text}")
    print(f"Эхо сообщение от {message.from_user.id}: {message.text}")

async def main():
    print("🚀 Запускаем простого тестового бота...")
    print(f"Токен: {BOT_TOKEN[:10]}...")
    
    try:
        # Запускаем поллинг
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
