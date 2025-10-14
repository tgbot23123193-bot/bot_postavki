#!/usr/bin/env python3
"""
Универсальный скрипт для полной очистки проекта:
- База данных (все таблицы)
- Файлы пользователей (браузеры, cookies, скриншоты)
"""

import asyncio
import sys

from clear_database import clear_all_tables
from clear_user_files import clear_user_files


async def full_cleanup():
    """Полная очистка проекта."""
    print("\n" + "="*60)
    print("🔥 ПОЛНАЯ ОЧИСТКА ПРОЕКТА")
    print("="*60)
    print("Будет выполнено:")
    print("  1. Очистка базы данных (все таблицы)")
    print("  2. Удаление файлов пользователей")
    print("\n⚠️  ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!")
    print("⚠️  Будут удалены ВСЕ данные!\n")
    print("="*60 + "\n")
    
    response = input("Введите 'CLEAR ALL' для подтверждения: ")
    
    if response == "CLEAR ALL":
        print("\n🚀 Начинаю полную очистку...\n")
        
        # Шаг 1: Очистка базы данных
        print("="*60)
        print("ШАГ 1/2: Очистка базы данных")
        print("="*60 + "\n")
        
        db_success = await clear_all_tables()
        
        if not db_success:
            print("\n⚠️  База данных не была полностью очищена.")
            proceed = input("Продолжить с очисткой файлов? (yes/no): ")
            if proceed.lower() != 'yes':
                print("\n❌ Операция прервана пользователем.\n")
                return False
        
        # Шаг 2: Очистка файлов пользователей
        print("\n" + "="*60)
        print("ШАГ 2/2: Очистка файлов пользователей")
        print("="*60 + "\n")
        
        clear_user_files()
        
        # Итоговый результат
        print("\n" + "="*60)
        print("🎉 ПОЛНАЯ ОЧИСТКА ЗАВЕРШЕНА!")
        print("="*60)
        print("✅ База данных очищена")
        print("✅ Файлы пользователей удалены")
        print("\nПроект возвращен в начальное состояние.")
        print("Можно запускать бота для свежего старта!\n")
        
        return True
    else:
        print("\n❌ Очистка отменена. Неверное подтверждение.\n")
        return False


async def main():
    """Главная функция."""
    success = await full_cleanup()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())


