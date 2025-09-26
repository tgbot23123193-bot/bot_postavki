# 🚀 Локальная настройка для разработки

## 📋 Быстрый старт

### 1. Создание тестового бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/botfather)
2. Отправьте команду `/newbot`
3. Введите имя для вашего тестового бота (например: `Test WB Bot`)
4. Введите username для бота (например: `test_wb_booking_bot`)
5. Скопируйте полученный токен

### 2. Настройка конфигурации

1. Откройте файл `config_local.env`
2. Замените `PUT_YOUR_BOT_TOKEN_HERE` на токен от BotFather:
   ```env
   TG_BOT_TOKEN=123456789:AABBCCDDEEFFgghhiijjkkllmmnnooppqq
   ```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Запуск приложения

```bash
cd wb_bot
python -m app.main
```

## 🔧 Конфигурация разработки

В локальной версии автоматически включены следующие настройки:

- ✅ **SQLite база данных** (`wb_bot.db`) вместо PostgreSQL
- ✅ **Платежи отключены** (`PAYMENT_PAYMENT_ENABLED=false`)
- ✅ **Debug режим** включен
- ✅ **JSON логирование** для отладки

## 🐛 Частые проблемы

### Ошибка "Token is invalid!"
- Убедитесь, что токен скопирован полностью
- Токен должен иметь формат: `числа:буквы_и_цифры`
- Создайте новый тестовый бот через @BotFather

### Ошибки базы данных
- База SQLite создается автоматически при первом запуске
- Файл сохраняется как `wb_bot.db` в корне проекта

### Проблемы с Redis
- Redis опционален для локальной разработки
- При отсутствии Redis используется in-memory хранилище

## 📝 Полезные команды

```bash
# Проверка конфигурации
python -c "from app.config import settings; print(f'Environment: {settings.environment}'); print(f'Payment enabled: {settings.payment.payment_enabled}')"

# Очистка базы данных
rm wb_bot.db

# Проверка логов
tail -f logs/app.log
```





