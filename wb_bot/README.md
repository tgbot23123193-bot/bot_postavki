# WB Auto-Booking Bot

🤖 **Профессиональный Telegram бот для автоматического бронирования поставок на Wildberries**

## 🚀 Возможности

### 🎯 Основной функционал
- 📊 **Мониторинг слотов** - отслеживание доступных слотов поставок в режиме реального времени
- 🤖 **Автобронирование** - автоматическое бронирование при появлении подходящих слотов
- 🔔 **Умные уведомления** - мгновенные уведомления о найденных слотах
- 📅 **Интерактивный календарь** - удобный выбор периодов мониторинга
- 📈 **Детальная аналитика** - статистика бронирований и эффективности

### ⚙️ Гибкие настройки
- 🎛 **Коэффициенты приемки** - фильтрация по стоимости (x1, x2, x3, x5)
- 📦 **Типы поставок** - короб или монопаллета
- 🚚 **Типы доставки** - прямая или транзитная
- ⏱ **Интервалы проверки** - от 1 секунды до 10 минут
- 🔑 **Множественные API ключи** - до 5 ключей для распределения нагрузки

### 🛡 Безопасность и надежность
- 🔐 **AES-256 шифрование** API ключей
- 🔄 **Retry механизм** с экспоненциальным backoff
- ⚡ **Circuit breaker** для защиты от каскадных сбоев
- 📊 **Мониторинг производительности** и health checks
- 🏗 **Микросервисная архитектура** для горизонтального масштабирования

## 🏗 Архитектура

### Технический стек
- **Python 3.11+** с современными фичами
- **aiogram 3.x** для Telegram бота
- **SQLAlchemy 2.0** + **AsyncPG** для базы данных
- **Redis** для кэширования и очередей
- **aiohttp** для HTTP клиента
- **Docker** + **Docker Compose** для развертывания

### Компоненты системы
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │────│  Monitoring     │────│  WB API Client  │
│   (aiogram)     │    │  Service        │    │  (aiohttp)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │   Encryption    │
│   Database      │    │     Cache       │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Быстрый запуск

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd wb_bot
```

### 2. Настройка окружения
```bash
# Скопируйте файл настроек
cp env.example .env

# Отредактируйте .env файл
nano .env
```

### 3. Обязательные настройки в .env
```bash
# Токен бота от @BotFather
TG_BOT_TOKEN=your_bot_token_here

# Ключ шифрования (32+ символов)
SECURITY_ENCRYPTION_KEY=your_encryption_key_here

# JWT секрет
SECURITY_JWT_SECRET=your_jwt_secret_here

# Пароль базы данных
DB_PASSWORD=your_secure_password
```

### 4. Запуск через Docker Compose
```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f wb_bot
```

### 5. Инициализация базы данных
```bash
# Выполнение миграций
docker-compose run --rm migration
```

## 🔧 Конфигурация

### Основные параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `MONITORING_MIN_CHECK_INTERVAL` | Минимальный интервал проверки (сек) | 30 |
| `MONITORING_MAX_CHECK_INTERVAL` | Максимальный интервал проверки (сек) | 1 |
| `MONITORING_CACHE_TTL` | TTL кэша в секундах | 5 |
| `MONITORING_MAX_CONCURRENT_REQUESTS` | Макс. параллельных запросов | 1000 |
| `WB_TIMEOUT` | Таймаут запросов к WB API | 30 |
| `WB_MAX_RETRIES` | Максимум повторов запросов | 3 |

### Режимы работы

#### Режим разработки
```bash
# Локальный запуск


```

#### Webhook режим
```bash
# Установите переменные для webhook
TG_WEBHOOK_URL=https://your-domain.com
TG_WEBHOOK_SECRET=your_secret

# Запуск
docker-compose up -d
```

## 📊 Мониторинг

### Health Check
```bash
curl http://localhost:8080/health
```

### Логи
```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f wb_bot
docker-compose logs -f postgres
docker-compose logs -f redis
```

### Метрики (опционально)
```bash
# Запуск с мониторингом
docker-compose --profile monitoring up -d

# Доступ к Grafana
open http://localhost:3000
# Логин: admin / пароль: admin (или из GRAFANA_PASSWORD)

# Доступ к Prometheus
open http://localhost:9090
```

## 🔐 Безопасность

### Генерация ключей шифрования
```python
import secrets
print("SECURITY_ENCRYPTION_KEY=" + secrets.token_urlsafe(32))
print("SECURITY_JWT_SECRET=" + secrets.token_urlsafe(32))
```

### Рекомендации по безопасности
- ✅ Используйте сильные пароли для базы данных
- ✅ Регулярно ротируйте API ключи
- ✅ Ограничьте доступ к серверу через firewall
- ✅ Используйте HTTPS для webhook'ов
- ✅ Регулярно обновляйте зависимости

## 🐛 Отладка

### Частые проблемы

#### Бот не отвечает
```bash
# Проверьте статус контейнера
docker-compose ps

# Проверьте логи
docker-compose logs wb_bot

# Проверьте подключение к БД
docker-compose exec postgres psql -U wb_user -d wb_bot -c "\dt"
```

#### Ошибки базы данных
```bash
# Пересоздание БД
docker-compose down -v
docker-compose up -d postgres
docker-compose run --rm migration
docker-compose up -d wb_bot
```

#### Проблемы с Redis
```bash
# Очистка кэша
docker-compose exec redis redis-cli FLUSHALL

# Проверка подключения
docker-compose exec redis redis-cli ping
```

### Режим отладки
```bash
# Включение подробных логов
DEBUG=true
LOG_LEVEL=DEBUG
DB_ECHO=true

docker-compose up -d
```

## 📈 Производительность

### Рекомендуемые характеристики сервера
- **CPU**: 2+ ядра
- **RAM**: 4+ GB
- **Диск**: 20+ GB SSD
- **Сеть**: стабильное соединение

### Оптимизация
- 🚀 Используйте SSD для базы данных
- 🔄 Настройте connection pooling
- 📊 Мониторьте метрики производительности
- ⚡ Оптимизируйте интервалы проверок

## 🤝 Поддержка

### Контакты
- 📧 Email: support@example.com
- 💬 Telegram: @support_username

### Полезные ссылки
- 📖 [Документация Wildberries API](https://openapi.wb.ru/)
- 🤖 [Документация aiogram](https://docs.aiogram.dev/)
- 🐳 [Docker Compose Reference](https://docs.docker.com/compose/)

## 📄 Лицензия

Этот проект лицензируется под MIT License. См. файл [LICENSE](LICENSE) для деталей.

---

**⚡ Готов к production использованию!**
