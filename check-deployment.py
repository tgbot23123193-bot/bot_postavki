#!/usr/bin/env python3
"""
Deployment Readiness Checker

Проверяет готовность проекта к деплою на Railway.
"""

import os
import sys
from pathlib import Path


def check_file_exists(filepath: str, required: bool = True) -> bool:
    """Проверяет существование файла."""
    exists = Path(filepath).exists()
    status = "✅" if exists else ("❌" if required else "⚠️")
    requirement = "ОБЯЗАТЕЛЬНО" if required else "ОПЦИОНАЛЬНО"
    print(f"{status} {filepath} ({requirement})")
    return exists


def check_docker_files() -> bool:
    """Проверяет Docker файлы."""
    print("\n🐳 DOCKER ФАЙЛЫ:")
    print("-" * 40)
    
    all_good = True
    all_good &= check_file_exists("Dockerfile", required=True)
    all_good &= check_file_exists(".dockerignore", required=False)
    
    return all_good


def check_railway_files() -> bool:
    """Проверяет файлы Railway."""
    print("\n🚂 RAILWAY ФАЙЛЫ:")
    print("-" * 40)
    
    all_good = True
    all_good &= check_file_exists("railway.json", required=True)
    all_good &= check_file_exists("railway.toml", required=False)
    all_good &= check_file_exists("config_railway.env", required=False)
    
    return all_good


def check_project_files() -> bool:
    """Проверяет основные файлы проекта."""
    print("\n📁 ОСНОВНЫЕ ФАЙЛЫ:")
    print("-" * 40)
    
    all_good = True
    all_good &= check_file_exists("requirements.txt", required=True)
    all_good &= check_file_exists(".gitignore", required=True)
    
    # Проверяем основной код
    if Path("wb_bot/app/main.py").exists():
        all_good &= check_file_exists("wb_bot/app/main.py", required=True)
    elif Path("app/main.py").exists():
        all_good &= check_file_exists("app/main.py", required=True)
    else:
        print("❌ main.py не найден ни в wb_bot/app/, ни в app/")
        all_good = False
    
    return all_good


def check_git_status() -> bool:
    """Проверяет статус Git."""
    print("\n📝 GIT СТАТУС:")
    print("-" * 40)
    
    if not Path(".git").exists():
        print("❌ Git не инициализирован")
        print("   Выполните: git init")
        return False
    
    # Проверяем наличие коммитов
    result = os.system("git log --oneline -1 > /dev/null 2>&1")
    if result != 0:
        print("⚠️  Нет коммитов")
        print("   Выполните: git add . && git commit -m 'Initial commit'")
        return False
    
    # Проверяем наличие remote
    result = os.system("git remote -v > /dev/null 2>&1")
    if result != 0:
        print("⚠️  Нет remote репозитория")
        print("   Выполните: git remote add origin <URL>")
        return False
    
    print("✅ Git настроен")
    return True


def check_dependencies() -> bool:
    """Проверяет зависимости."""
    print("\n📦 ЗАВИСИМОСТИ:")
    print("-" * 40)
    
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt не найден")
        return False
    
    with open("requirements.txt", "r", encoding="utf-8") as f:
        requirements = f.read().lower()
    
    critical_deps = [
        "aiogram",
        "asyncpg", 
        "sqlalchemy",
        "aiohttp",
        "pydantic",
        "redis",
        "playwright"
    ]
    
    missing_deps = []
    for dep in critical_deps:
        if dep not in requirements:
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"❌ Отсутствуют зависимости: {', '.join(missing_deps)}")
        return False
    
    print("✅ Все критичные зависимости найдены")
    return True


def print_deployment_checklist():
    """Печатает чеклист для деплоя."""
    print("\n📋 ЧЕКЛИСТ ДЛЯ ДЕПЛОЯ:")
    print("="*50)
    print("□ Получить токен от @BotFather")
    print("□ Сгенерировать ключи безопасности (railway-setup.py)")
    print("□ Создать репозиторий на GitHub")
    print("□ Запушить код: git push origin main")
    print("□ Создать проект на Railway")
    print("□ Добавить PostgreSQL и Redis")
    print("□ Настроить переменные окружения")
    print("□ Проверить логи деплоя")
    print("□ Протестировать бот в Telegram")


def main():
    """Основная функция проверки."""
    print("🔍 ПРОВЕРКА ГОТОВНОСТИ К ДЕПЛОЮ")
    print("="*50)
    
    all_checks = []
    
    # Запускаем проверки
    all_checks.append(check_project_files())
    all_checks.append(check_docker_files())  
    all_checks.append(check_railway_files())
    all_checks.append(check_dependencies())
    all_checks.append(check_git_status())
    
    print("\n" + "="*50)
    
    if all(all_checks):
        print("🎉 ПРОЕКТ ГОТОВ К ДЕПЛОЮ!")
        print("✅ Все проверки пройдены успешно")
        print("\nСледующие шаги:")
        print("1. python railway-setup.py")
        print("2. git push origin main") 
        print("3. Создать проект на Railway")
    else:
        print("❌ ПРОЕКТ НЕ ГОТОВ К ДЕПЛОЮ")
        print("⚠️  Исправьте ошибки выше")
        print_deployment_checklist()
        return False
    
    print_deployment_checklist()
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
