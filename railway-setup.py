#!/usr/bin/env python3
"""
Railway Environment Variables Setup Script

Генерирует необходимые ключи безопасности и предоставляет
готовые команды для настройки переменных окружения в Railway.
"""

import secrets
import sys


def generate_key(length: int = 32) -> str:
    """Генерирует криптографически стойкий ключ."""
    return secrets.token_urlsafe(length)


def print_header(title: str):
    """Печатает заголовок секции."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def main():
    """Основная функция генерации ключей и инструкций."""
    print("🚀 Railway Deployment Setup for WB Auto-Booking Bot")
    print("="*60)
    
    # Генерация ключей
    encryption_key = generate_key(32)
    jwt_secret = generate_key(32)
    webhook_secret = generate_key(16)
    payment_webhook_secret = generate_key(32)
    
    print_header("🔐 СГЕНЕРИРОВАННЫЕ КЛЮЧИ БЕЗОПАСНОСТИ")
    print(f"SECURITY_ENCRYPTION_KEY: {encryption_key}")
    print(f"SECURITY_JWT_SECRET: {jwt_secret}")
    print(f"TG_WEBHOOK_SECRET: {webhook_secret}")
    print(f"PAYMENT_WEBHOOK_SECRET: {payment_webhook_secret}")
    
    print("\n⚠️  ВАЖНО: Сохраните эти ключи в безопасном месте!")
    
    print_header("📋 ИНСТРУКЦИИ ПО НАСТРОЙКЕ RAILWAY")
    
    print("1. Зайдите в Railway Dashboard")
    print("2. Откройте ваш проект")
    print("3. Перейдите в Variables")
    print("4. Добавьте следующие переменные:")
    print()
    
    # Обязательные переменные
    print("🔴 ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ:")
    print("-" * 30)
    
    variables = [
        ("TG_BOT_TOKEN", "ВАШ_ТОКЕН_ОТ_BOTFATHER", "Получите от @BotFather в Telegram"),
        ("SECURITY_ENCRYPTION_KEY", encryption_key, "Ключ шифрования (сгенерирован)"),
        ("SECURITY_JWT_SECRET", jwt_secret, "JWT секрет (сгенерирован)"),
        ("TG_WEBHOOK_SECRET", webhook_secret, "Webhook секрет (сгенерирован)"),
        ("PAYMENT_WEBHOOK_SECRET", payment_webhook_secret, "Webhook секрет для ЮKassa (сгенерирован)")
    ]
    
    for var_name, var_value, description in variables:
        print(f"{var_name}={var_value}")
        print(f"  └─ {description}")
        print()
    
    # ЮKassa переменные  
    print("💳 ПЕРЕМЕННЫЕ ЮKASSA:")
    print("-" * 30)
    
    yookassa_vars = [
        ("PAYMENT_ENABLED", "true", "🔥 ГЛАВНАЯ: включить/отключить платежи (false = БЕСПЛАТНО)"),
        ("PAYMENT_YOOKASSA_SHOP_ID", "ВАШИ_SHOP_ID_ИЗ_ЮKASSA", "Shop ID из личного кабинета ЮKassa"),
        ("PAYMENT_YOOKASSA_SECRET_KEY", "ВАШ_SECRET_KEY_ИЗ_ЮKASSA", "Secret Key из личного кабинета ЮKassa"),
        ("PAYMENT_TEST_MODE", "false", "Тестовый режим (true для тестов)")
    ]
    
    for var_name, var_value, description in yookassa_vars:
        print(f"{var_name}={var_value}")
        print(f"  └─ {description}")
        print()
    
    # Опциональные переменные
    print("🟡 ОПЦИОНАЛЬНЫЕ ПЕРЕМЕННЫЕ:")
    print("-" * 30)
    
    optional_vars = [
        ("TG_ADMIN_IDS", "123456789,987654321", "ID администраторов (ваш Telegram ID)"),
        ("ENVIRONMENT", "production", "Окружение"),
        ("DEBUG", "false", "Режим отладки"),
        ("LOG_LEVEL", "INFO", "Уровень логирования")
    ]
    
    for var_name, var_value, description in optional_vars:
        print(f"{var_name}={var_value}")
        print(f"  └─ {description}")
        print()
    
    print_header("🤖 КАК ПОЛУЧИТЬ TELEGRAM BOT TOKEN")
    print("1. Откройте Telegram и найдите @BotFather")
    print("2. Отправьте команду /newbot")
    print("3. Следуйте инструкциям для создания бота")
    print("4. Скопируйте полученный токен")
    print("5. Вставьте его в переменную TG_BOT_TOKEN")
    
    print_header("💳 КАК ПОЛУЧИТЬ КЛЮЧИ ЮKASSA")
    print("1. Зарегистрируйтесь на yookassa.ru")
    print("2. Пройдите верификацию")
    print("3. В личном кабинете:")
    print("   • Настройки → Магазин → скопируйте Shop ID")
    print("   • Настройки → API ключи → создайте Secret Key")
    print("4. Добавьте ключи в переменные Railway")
    print("5. Для тестов используйте песочницу ЮKassa")
    
    print_header("📍 КАК УЗНАТЬ ВАШ TELEGRAM ID")
    print("1. Откройте Telegram и найдите @userinfobot")
    print("2. Отправьте команду /start")
    print("3. Скопируйте ваш ID")
    print("4. Добавьте его в переменную TG_ADMIN_IDS")
    
    print_header("🔄 АВТОМАТИЧЕСКИЕ ПЕРЕМЕННЫЕ RAILWAY")
    print("Railway автоматически добавит:")
    print("• DATABASE_URL - подключение к PostgreSQL")
    print("• REDIS_URL - подключение к Redis")
    print("• RAILWAY_PUBLIC_DOMAIN - домен вашего приложения")
    
    print_header("🚀 ПРОВЕРКА ДЕПЛОЯ")
    print("После настройки переменных:")
    print("1. Railway автоматически пересоберет приложение")
    print("2. Проверьте логи деплоя в Railway Dashboard")
    print("3. Найдите ваш бот в Telegram и отправьте /start")
    print("4. Проверьте работу бота")
    
    print_header("📞 ПОДДЕРЖКА")
    print("Если что-то не работает:")
    print("• Проверьте логи в Railway Dashboard")
    print("• Убедитесь что все переменные заданы")
    print("• Проверьте валидность TG_BOT_TOKEN")
    print("• Убедитесь что PostgreSQL и Redis добавлены в проект")
    
    print("\n🎉 Удачного деплоя!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
