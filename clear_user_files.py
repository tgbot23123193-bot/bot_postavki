#!/usr/bin/env python3
"""
Скрипт для очистки файлов пользователей (браузерные данные, cookies, скриншоты).
"""

import os
import shutil
import glob
from pathlib import Path

def clear_user_files():
    """Очистка всех файлов пользователей."""
    print("\n" + "="*60)
    print("🧹 ОЧИСТКА ФАЙЛОВ ПОЛЬЗОВАТЕЛЕЙ")
    print("="*60)
    
    # Паттерны для поиска
    patterns = [
        'wb_user_data_*',      # Папки с данными браузеров
        'wb_cookies_*.json',   # Файлы cookies
        'screenshots_*'        # Папки со скриншотами
    ]
    
    total_deleted = 0
    
    for pattern in patterns:
        print(f"\n🔍 Ищу: {pattern}")
        matches = glob.glob(pattern)
        
        if not matches:
            print(f"   ℹ️  Файлы не найдены")
            continue
        
        for path in matches:
            path_obj = Path(path)
            try:
                if path_obj.is_dir():
                    # Подсчитываем файлы в папке
                    file_count = sum(1 for _ in path_obj.rglob('*') if _.is_file())
                    shutil.rmtree(path)
                    print(f"   ✅ Удалена папка: {path} ({file_count} файлов)")
                    total_deleted += 1
                elif path_obj.is_file():
                    path_obj.unlink()
                    print(f"   ✅ Удален файл: {path}")
                    total_deleted += 1
            except Exception as e:
                print(f"   ❌ Ошибка при удалении {path}: {e}")
    
    print("\n" + "="*60)
    print(f"📊 Удалено элементов: {total_deleted}")
    print("="*60 + "\n")
    
    if total_deleted > 0:
        print("✅ Файлы пользователей успешно очищены!\n")
    else:
        print("ℹ️  Файлы пользователей не найдены (папка уже чистая)\n")


def confirm_and_clear():
    """Запрос подтверждения и очистка."""
    print("\n" + "="*60)
    print("⚠️  ВНИМАНИЕ: ОЧИСТКА ФАЙЛОВ ПОЛЬЗОВАТЕЛЕЙ")
    print("="*60)
    print("Будут удалены:")
    print("  • Папки wb_user_data_* (данные браузеров)")
    print("  • Файлы wb_cookies_*.json (cookies)")
    print("  • Папки screenshots_* (скриншоты)")
    print("\n⚠️  ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!")
    print("⚠️  Пользователи потеряют авторизацию в браузере!\n")
    print("="*60 + "\n")
    
    response = input("Введите 'YES' для подтверждения: ")
    
    if response.upper() == "YES":
        print("\n🚀 Начинаю очистку файлов...\n")
        clear_user_files()
        return True
    else:
        print("\n❌ Очистка отменена.\n")
        return False


if __name__ == "__main__":
    confirm_and_clear()


