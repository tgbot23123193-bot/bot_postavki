#!/usr/bin/env python3
"""
Скрипт для перезапуска бота с корректными настройками.
"""

import asyncio
import signal
import sys
from app.main import BotApplication

async def main():
    print("🔄 Перезапускаем бота с исправлениями...")
    
    app = BotApplication()
    
    # Обработчик сигналов
    def signal_handler(signum, frame):
        print(f"\n⏹️ Получен сигнал {signum}, завершение работы...")
        asyncio.create_task(app.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Инициализация приложения
        await app.initialize()
        print("✅ Бот инициализирован успешно!")
        
        # Запуск в режиме поллинга
        print("🚀 Запускаем поллинг...")
        await app.start_polling()
        
    except KeyboardInterrupt:
        print("\n⏸️ Остановка по Ctrl+C")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    finally:
        await app.cleanup()
        print("🏁 Завершение работы")

if __name__ == "__main__":
    asyncio.run(main())
