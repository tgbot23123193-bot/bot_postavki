# 🚀 Быстрые команды

## 🗑️ Очистка данных

### Полная очистка (БД + файлы)
```bash
python clear_all.py
# Подтверждение: CLEAR ALL
```

### Очистить только базу данных
```bash
python clear_database.py
# Подтверждение: DELETE ALL
```

### Очистить только файлы пользователей
```bash
python clear_user_files.py
# Подтверждение: YES
```

---

## 🧪 Тестирование

### Тест мультисессии
```bash
python test_multisession.py
```

### Запуск бота (локально)
```bash
python -m wb_bot.app.main
```

---

## 📊 Проверка базы данных

### Проверить подключение к БД
```bash
python -c "import asyncio; from wb_bot.app.database import init_database, health_check, close_database; asyncio.run((lambda: (init_database(), print('✅ База данных доступна' if health_check() else '❌ База данных недоступна'), close_database()))())"
```

### Посчитать записи в таблицах
```bash
python -c "
import asyncio
from sqlalchemy import text
from wb_bot.app.database import init_database, get_session, close_database

async def check():
    await init_database()
    async with get_session() as session:
        tables = ['users', 'api_keys', 'monitoring_tasks', 'booking_tasks', 'booking_results', 'browser_sessions']
        for table in tables:
            result = await session.execute(text(f'SELECT COUNT(*) FROM {table}'))
            count = result.scalar()
            print(f'{table:30s}: {count} записей')
    await close_database()

asyncio.run(check())
"
```

---

## 🔧 Установка и настройка

### Установить зависимости
```bash
pip install -r requirements.txt
```

### Установить Playwright браузеры
```bash
playwright install firefox
```

### Применить миграции БД
```bash
cd wb_bot
alembic upgrade head
```

---

## 📁 Файловая структура

После работы с ботом создаются:
- `wb_user_data_{user_id}/` - данные браузера пользователя
- `wb_cookies_{user_id}.json` - cookies пользователя
- `screenshots_{user_id}/` - скриншоты пользователя

---

## 🆘 Решение проблем

### Браузер не запускается
```bash
playwright install --force firefox
```

### Ошибка подключения к БД
1. Проверьте `config_local.env`
2. Убедитесь что PostgreSQL запущен
3. Проверьте `DATABASE_URL`

### Очистить всё и начать заново
```bash
# Полная очистка
python clear_all.py

# Переустановить браузеры
playwright install --force firefox

# Применить миграции
cd wb_bot
alembic upgrade head

# Запустить бота
python -m wb_bot.app.main
```

---

## 📚 Дополнительная документация

- `DATABASE_MANAGEMENT.md` - управление базой данных
- `MULTISESSION_FIX.md` - как работает мультисессия
- `TESTING_GUIDE.md` - руководство по тестированию
- `README.md` - основная документация


