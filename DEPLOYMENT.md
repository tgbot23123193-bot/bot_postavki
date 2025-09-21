# 🚀 Деплой WB Auto-Booking Bot на Railway

## 📋 Предварительные требования

1. **GitHub аккаунт** - для подключения репозитория
2. **Railway аккаунт** - зарегистрируйтесь на [railway.app](https://railway.app)
3. **Telegram Bot Token** - получите от [@BotFather](https://t.me/botfather)

## 🔧 Подготовка проекта

### 1. Загрузка на GitHub

```bash
# Инициализация git репозитория (если еще не сделано)
git init

# Добавление всех файлов
git add .

# Коммит изменений
git commit -m "Initial commit: WB Auto-Booking Bot ready for Railway deployment"

# Добавление remote репозитория (замените на ваш)
git remote add origin https://github.com/yourusername/wb-bot.git

# Пуш в GitHub
git push -u origin main
```

### 2. Создание необходимых ключей

Сгенерируйте секретные ключи для безопасности:

```bash
# Для SECURITY_ENCRYPTION_KEY (32+ символов)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Для SECURITY_JWT_SECRET (32+ символов) 
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Для TG_WEBHOOK_SECRET (если используете webhook)
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

## 🚂 Деплой на Railway

### 1. Создание проекта

1. Зайдите на [railway.app](https://railway.app)
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Выберите ваш репозиторий `wb-bot`

### 2. Добавление баз данных

Railway автоматически обнаружит `railway.json` и предложит добавить:

1. **PostgreSQL** - для основной базы данных
2. **Redis** - для кэширования и очередей

Подтвердите добавление обеих служб.

### 3. Настройка переменных окружения

В Railway Dashboard перейдите в **Variables** и добавьте:

#### Обязательные переменные:

```env
# Токен бота (получите от @BotFather)
TG_BOT_TOKEN=1234567890:ABCDefGhIjKlMnOpQrStUvWxYz

# Ключи безопасности (сгенерируйте как указано выше)
SECURITY_ENCRYPTION_KEY=ваш_сгенерированный_32_символьный_ключ
SECURITY_JWT_SECRET=ваш_сгенерированный_jwt_секрет

# Webhook настройки (опционально)
TG_WEBHOOK_SECRET=ваш_webhook_секрет

# ID администраторов (ваш Telegram ID)
TG_ADMIN_IDS=123456789,987654321
```

#### Railway автоматически добавит:

- `DATABASE_URL` - PostgreSQL подключение
- `REDIS_URL` - Redis подключение  
- `RAILWAY_PUBLIC_DOMAIN` - домен вашего приложения

### 4. Настройка webhook (опционально)

Если хотите использовать webhook вместо polling:

1. После деплоя получите ваш Railway домен
2. Добавьте переменную:
   ```env
   TG_WEBHOOK_URL=https://ваш-домен.railway.app/webhook
   ```

## 🔍 Проверка деплоя

### 1. Логи деплоя

В Railway Dashboard откройте вкладку **"Deployments"** и проверьте логи:

```
✅ Database connection initialized successfully
✅ Bot initialized successfully  
✅ Starting polling... (или webhook mode)
```

### 2. Тестирование бота

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Проверьте ответ бота

## 🛠️ Управление

### Просмотр логов

```bash
# Установите Railway CLI
npm install -g @railway/cli

# Войдите в аккаунт
railway login

# Подключитесь к проекту
railway link

# Просмотр логов в реальном времени
railway logs
```

### Обновление кода

```bash
# Внесите изменения в код
git add .
git commit -m "Update: описание изменений"
git push

# Railway автоматически пересоберет и задеплоит
```

### Переменные окружения

Изменяйте через Railway Dashboard:
- Project → Variables → Add/Edit

## 🔧 Полезные команды

### Подключение к базе данных

```bash
# Получение DATABASE_URL
railway variables

# Подключение к PostgreSQL
railway run psql $DATABASE_URL
```

### Локальная разработка с Railway

```bash
# Загрузка переменных из Railway
railway run python -m wb_bot.app.main
```

## 🚨 Troubleshooting

### Проблема: Бот не запускается

1. Проверьте логи в Railway Dashboard
2. Убедитесь, что все обязательные переменные заданы
3. Проверьте валидность `TG_BOT_TOKEN`

### Проблема: Ошибка базы данных

1. Убедитесь, что PostgreSQL добавлен в проект
2. Проверьте переменную `DATABASE_URL`
3. Проверьте миграции в логах

### Проблема: Webhook не работает

1. Проверьте `TG_WEBHOOK_URL` в переменных
2. Убедитесь, что домен доступен
3. Проверьте `TG_WEBHOOK_SECRET`

## 📊 Мониторинг

Railway предоставляет:
- **Metrics** - CPU, Memory, Network
- **Logs** - логи приложения в реальном времени
- **Deployments** - история деплоев

**Примечание**: Health checks отключены для стабильности деплоя.

## 💰 Стоимость

Railway предлагает:
- **Hobby Plan** - $5/месяц на пользователя
- **Pro Plan** - $20/месяц на пользователя

Включает PostgreSQL и Redis на тарифе.

## 🔐 Безопасность

✅ **Что сделано:**
- Переменные окружения для секретов
- Шифрование API ключей пользователей
- Непривилегированный пользователь в Docker
- Health checks

⚠️ **Рекомендации:**
- Регулярно обновляйте зависимости
- Мониторьте логи на подозрительную активность
- Используйте сильные ключи шифрования

## 🎉 Готово!

Ваш WB Auto-Booking Bot теперь работает на Railway и готов к использованию!

**Полезные ссылки:**
- [Railway Documentation](https://docs.railway.app/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Wildberries API](https://suppliers-api.wildberries.ru/)
