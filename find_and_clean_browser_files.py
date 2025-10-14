#!/usr/bin/env python3
"""
Поиск и удаление ВСЕХ файлов и папок браузеров
"""
import os
import shutil
from pathlib import Path

def find_and_clean():
    print("\n🔍 Ищу файлы и папки браузеров...\n")
    
    # Ищем во всех возможных местах
    search_paths = [
        Path("."),  # Текущая папка
        Path("wb_bot"),  # Папка wb_bot
    ]
    
    patterns = [
        "wb_user_data_*",
        "wb_cookies_*.json",
        "screenshots_*"
    ]
    
    total_deleted = 0
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
            
        print(f"📂 Проверяю: {search_path.absolute()}")
        
        for pattern in patterns:
            # Ищем все совпадения
            matches = list(search_path.glob(pattern))
            
            if matches:
                print(f"\n  Найдено по паттерну '{pattern}': {len(matches)}")
                
                for item in matches:
                    try:
                        if item.is_dir():
                            # Считаем файлы в папке
                            file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                            shutil.rmtree(item)
                            print(f"    ✅ Удалена папка: {item.name} ({file_count} файлов)")
                            total_deleted += 1
                        elif item.is_file():
                            item.unlink()
                            print(f"    ✅ Удален файл: {item.name}")
                            total_deleted += 1
                    except Exception as e:
                        print(f"    ❌ Ошибка удаления {item.name}: {e}")
    
    print(f"\n{'='*60}")
    print(f"ВСЕГО УДАЛЕНО: {total_deleted} элементов")
    print(f"{'='*60}\n")
    
    if total_deleted > 0:
        print("✅ Все файлы браузеров удалены!")
    else:
        print("ℹ️  Файлы браузеров не найдены (всё чисто)")

if __name__ == "__main__":
    find_and_clean()



