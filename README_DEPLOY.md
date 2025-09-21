# 🚀 Быстрый деплой на Railway

## ⚡ Быстрый старт (5 минут)

### 1. Подготовка ключей
```bash
python railway-setup.py
```
Скопируйте сгенерированные ключи!

### 2. GitHub
```bash
git add .
git commit -m "Ready for Railway deployment"
git push origin main
```

### 3. Railway
1. [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub repo** → выберите ваш репозиторий
3. Добавить **PostgreSQL** и **Redis** (автоматически предложит)
4. **Variables** → добавить ключи из шага 1

### 4. Обязательные переменные
```env
TG_BOT_TOKEN=ваш_токен_от_botfather
SECURITY_ENCRYPTION_KEY=сгенерированный_ключ
SECURITY_JWT_SECRET=сгенерированный_jwt
TG_WEBHOOK_SECRET=сгенерированный_webhook
```

### 5. Проверка
- Проверьте логи деплоя в Railway
- Найдите бот в Telegram → `/start`

## 📁 Что создано для деплоя

- ✅ **Dockerfile** - контейнеризация приложения
- ✅ **railway.json** - конфигурация Railway
- ✅ **config_railway.env** - шаблон переменных окружения  
- ✅ **.gitignore** - игнорируемые файлы
- ✅ **.dockerignore** - файлы для Docker
- ✅ **DEPLOYMENT.md** - подробная инструкция
- ✅ **railway-setup.py** - генератор ключей

## 🔧 Особенности

- **Multi-stage Docker build** для оптимизации
- **Health checks** для мониторинга
- **Автоматическая настройка PostgreSQL/Redis**
- **Webhook поддержка** для production
- **Безопасное хранение секретов**

## 🆘 Проблемы?

1. **Бот не запускается** → Проверьте `TG_BOT_TOKEN`
2. **Ошибка базы данных** → Убедитесь что PostgreSQL добавлен
3. **Webhook не работает** → Проверьте домен в переменных

## 📚 Документация

- **DEPLOYMENT.md** - полная инструкция
- **QUICK_START.md** - локальный запуск
- **cursor_ai_tz.md** - техническое задание

---

**🎯 Результат:** Рабочий WB Auto-Booking Bot на Railway за 5 минут!
