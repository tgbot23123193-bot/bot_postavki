# ⚡ Быстрое Развертывание на Railway

## 🎯 За 5 минут к запуску!

### Шаг 1: Подготовка Railway (2 минуты)

1. **Создайте проект на Railway**
   - Перейдите на [railway.app](https://railway.app/)
   - Войдите через GitHub
   - Нажмите **"New Project"**
   - Выберите **"Deploy from GitHub repo"**
   - Выберите ваш репозиторий

2. **Добавьте PostgreSQL**
   - В проекте нажмите **"+ New"**
   - Выберите **"Database"** → **"Add PostgreSQL"**
   - ✅ Готово! Railway автоматически свяжет базу с вашим сервисом

---

### Шаг 2: Переменные окружения (2 минуты)

1. **Откройте Variables**
   - Выберите ваш сервис (не базу данных)
   - Перейдите в **"Variables"**
   - Нажмите **"Raw Editor"** (для быстрого добавления)

2. **Скопируйте и вставьте всё это**:

```env
TG_BOT_TOKEN=8297598368:AAFAjtygKnsIwocwbdC4qTr-lmEFRZ8k4qA
TG_WEBHOOK_SECRET=3dsY5-Kw6z6FYMHbf4sSKQ
SECURITY_ENCRYPTION_KEY=ccKZeb26sLwuV_bvzY48nb3yeFrkFxgqZgnns1l6RhU1
SECURITY_JWT_SECRET=jBtx0ciYj0MYPjpXbPpRwpNy-3TW8z3HQZdtQbDyFck
DATABASE_ECHO=false
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
REDISTRIBUTION_MAX_ATTEMPTS=0
REDISTRIBUTION_RETRY_SECONDS=35
REDISTRIBUTION_ACTIVE_RETRY_SECONDS=15
REDISTRIBUTION_BOOKING_PERIODS=8:55-9:10,9:55-10:10
REDISTRIBUTION_AUTO_RETRY=true
WB_BASE_URL=https://suppliers-api.wildberries.ru
WB_TIMEOUT=30
WB_MAX_RETRIES=3
WB_RATE_LIMIT_DELAY=60
MONITORING_DEFAULT_INTERVAL_SEC=30
MONITORING_MAX_API_KEYS_PER_USER=5
MONITORING_TRIAL_BOOKINGS_LIMIT=2
PAYMENT_ENABLED=false
PAYMENT_TEST_MODE=true
PAYMENT_YOOKASSA_SHOP_ID=1156264
PAYMENT_YOOKASSA_SECRET_KEY=test_gM4zhyQi_AjlrrRB_RafZNAB0xhjpqgABP2RMsIog8A
PAYMENT_WEBHOOK_SECRET=fLOA1tMFLaOoYsLqeXXc0OV2my9Hhpo8aXkLU9696RE
PAYMENT_CURRENCY=RUB
PAYMENT_BOOKING_COST=10.0
PAYMENT_MIN_DEPOSIT_AMOUNT=500.0
PAYMENT_MAX_DEPOSIT_AMOUNT=50000.0
```

3. **Нажмите "Save"** и дождитесь деплоя

---

### Шаг 3: Настройка Webhook (1 минута)

⚠️ **ВАЖНО**: Выполните после первого успешного деплоя!

1. **Получите домен**
   - **Settings** → **Networking** → **Generate Domain**
   - Скопируйте ваш домен (например: `your-app-production.up.railway.app`)

2. **Добавьте TG_WEBHOOK_URL**
   - Вернитесь в **Variables**
   - Добавьте новую переменную:
   ```
   TG_WEBHOOK_URL=https://your-app-production.up.railway.app/webhook
   ```
   - Замените `your-app-production.up.railway.app` на ваш реальный домен!

3. **Сохраните** - Railway автоматически передеплоит

---

### ✅ Проверка работы

1. **Проверьте логи**
   - Перейдите в **"Deployments"**
   - Выберите последний деплой
   - Смотрите логи - должно быть:
   ```
   ✅ "Bot application initialized successfully"
   ✅ "Starting in webhook mode"
   ✅ "Webhook started at https://..."
   ```

2. **Проверьте Health Check**
   - Откройте: `https://ваш-домен.up.railway.app/health`
   - Должно показать: `{"status": "healthy", "service": "wb-bot"}`

3. **Проверьте бота в Telegram**
   - Найдите вашего бота
   - Отправьте `/start`
   - Бот должен ответить! 🎉

---

## 🐛 Быстрое решение проблем

### Бот не отвечает?
```bash
# Проверьте webhook командой:
curl https://api.telegram.org/bot8297598368:AAFAjtygKnsIwocwbdC4qTr-lmEFRZ8k4qA/getWebhookInfo

# Должно быть:
# "url": "https://ваш-домен.up.railway.app/webhook"
# "pending_update_count": 0
```

### Playwright ошибки?
- Проверьте логи на наличие "Installing Playwright browsers..."
- Увеличьте RAM: **Settings** → **Resources** → 2GB минимум

### Database connection error?
- Убедитесь, что PostgreSQL сервис запущен
- Railway должен автоматически добавить `DATABASE_URL`
- Перезапустите сервис

---

## 📊 Полезные команды

### Проверка webhook
```bash
curl https://api.telegram.org/bot8297598368:AAFAjtygKnsIwocwbdC4qTr-lmEFRZ8k4qA/getWebhookInfo
```

### Проверка здоровья
```bash
curl https://ваш-домен.up.railway.app/health
```

### Удалить webhook (для тестирования)
```bash
curl https://api.telegram.org/bot8297598368:AAFAjtygKnsIwocwbdC4qTr-lmEFRZ8k4qA/deleteWebhook
```

---

## 🎉 Готово!

Ваш бот работает на Railway 24/7!

**Следующие шаги**:
1. ✅ Протестируйте `/start` в Telegram
2. ✅ Добавьте задачу автобронирования
3. ✅ Проверьте мониторинг с API ключом
4. ✅ Настройте уведомления

---

## 📚 Дополнительная документация

- **Полное руководство**: `RAILWAY_DEPLOYMENT_GUIDE.md`
- **Все переменные**: `RAILWAY_ENV_VARIABLES.txt`
- **Локальная настройка**: `LOCAL_SETUP.md`

**Успехов! 🚀**

