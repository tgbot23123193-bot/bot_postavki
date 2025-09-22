# 🎯 СТАРТ: Деплой WB Bot на Railway

## 🚀 Проект готов к деплою!

Все необходимые файлы созданы и настроены. Следуйте инструкциям ниже.

## 📋 ЧТО БЫЛО ПОДГОТОВЛЕНО

✅ **Dockerfile** - для контейнеризации приложения  
✅ **railway.json** - конфигурация Railway  
✅ **config_railway.env** - шаблон переменных окружения  
✅ **.gitignore** - игнорируемые файлы  
✅ **railway-setup.py** - генератор ключей безопасности  
✅ **check-deployment.py** - проверка готовности  
✅ **DEPLOYMENT.md** - подробная инструкция  

## ⚡ БЫСТРЫЙ СТАРТ (3 шага)

### 1️⃣ Сгенерируйте ключи
```bash
python railway-setup.py
```
📝 **Сохраните** сгенерированные ключи!

### 2️⃣ Загрузите на GitHub
```bash
# Добавьте remote (замените URL на ваш)
git remote add origin https://github.com/ВАШЕ_ИМЯ/wb-bot.git

# Загрузите код
git push -u origin main
```

### 3️⃣ Задеплойте на Railway
1. Зайдите на [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub repo**
3. Выберите ваш репозиторий
4. Railway автоматически предложит добавить **PostgreSQL** и **Redis** ✅
5. В **Variables** добавьте ключи из шага 1

## 🔑 ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ

Добавьте в Railway Variables:

```env
TG_BOT_TOKEN=получите_от_@BotFather
SECURITY_ENCRYPTION_KEY=MCE7AaXntGlOs-TsbwZtvmTr2v5ZLgQp313qJ41uxx0
SECURITY_JWT_SECRET=Dq024Qv6y1uZyy7afd4cVpT01dTkPzFcAofFB3e6oQc
TG_WEBHOOK_SECRET=3dsY5-Kw6z6FYMHbf4sSKQ
PAYMENT_WEBHOOK_SECRET=fLOA1tMFLaOoYsLqeXXc0OV2my9Hhpo8aXkLU9696RE
PAYMENT_YOOKASSA_SHOP_ID=ваш_shop_id
PAYMENT_YOOKASSA_SECRET_KEY=ваш_secret_key
PAYMENT_ENABLED=true
PAYMENT_TEST_MODE=false
```

📋 **Инструкция**: см. файл `YOOKASSA_SETUP.md`

## 🔧 ПОЛЕЗНЫЕ КОМАНДЫ

```bash
# Проверить готовность к деплою
python check-deployment.py

# Сгенерировать новые ключи
python railway-setup.py

# Посмотреть статус Git
git status
```

## 📚 ДОКУМЕНТАЦИЯ

- **README_DEPLOY.md** - краткое руководство
- **DEPLOYMENT.md** - подробная инструкция  
- **QUICK_START.md** - локальный запуск
- **cursor_ai_tz.md** - техническое задание

## 🆘 ПРОБЛЕМЫ?

1. **Токен бота** → Получите от [@BotFather](https://t.me/botfather)
2. **Ваш Telegram ID** → Узнайте у [@userinfobot](https://t.me/userinfobot) 
3. **Ошибки деплоя** → Проверьте логи в Railway Dashboard
4. **Бот не отвечает** → Убедитесь что PostgreSQL/Redis добавлены

## 🎉 РЕЗУЛЬТАТ

После деплоя у вас будет:
- ✅ Работающий Telegram бот на Railway
- ✅ Автоматическое бронирование слотов WB
- ✅ Безопасное хранение API ключей пользователей
- ✅ **Система платежей с ЮKassa**
- ✅ **Личный кабинет с балансом**
- ✅ **Автоматическое списание за бронирования**
- ✅ Мониторинг и логирование
- ✅ Автоматические перезапуски
- ✅ Упрощенная конфигурация без health checks

---

**🚀 Время деплоя: ~5 минут**  
**💰 Стоимость: $5/месяц на Railway**  
**⚡ Готово к использованию!**
