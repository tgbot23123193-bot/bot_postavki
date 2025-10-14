# Управление базой данных

## 🗑️ Очистка проекта

### 🔥 Полная очистка всего (БД + файлы)

**Рекомендуется:** Очистить и базу данных, и файлы пользователей одной командой:

```bash
python clear_all.py
```

Вам будет предложено ввести `CLEAR ALL` для подтверждения.

### Очистка только базы данных

Очистить только БД (с подтверждением):

```bash
python clear_database.py
```

Вам будет предложено ввести `DELETE ALL` для подтверждения.

**Что будет удалено:**
- ✅ Все пользователи
- ✅ Все API ключи
- ✅ Все задачи мониторинга
- ✅ Все результаты бронирования
- ✅ Все браузерные сессии
- ✅ Все задачи бронирования

### Быстрая очистка (без подтверждения)

⚠️ **ОПАСНО! Используйте только если уверены!**

```bash
# Вариант 1: Через Python скрипт
python -c "import asyncio; from clear_database import clear_all_tables; asyncio.run(clear_all_tables())"

# Вариант 2: Через psql (если есть доступ к PostgreSQL)
psql $DATABASE_URL -c "TRUNCATE TABLE users, api_keys, monitoring_tasks, booking_tasks, booking_results, browser_sessions CASCADE;"
```

### Очистка с сохранением структуры

Скрипт `clear_database.py` использует `TRUNCATE TABLE CASCADE`, что:
- ✅ Удаляет все данные
- ✅ Сбрасывает счетчики AUTO_INCREMENT
- ✅ Сохраняет структуру таблиц (схему)
- ✅ Не удаляет таблицы

## 🔄 Пересоздание базы данных с нуля

Если нужно полностью пересоздать базу данных:

### Вариант 1: Через Alembic (рекомендуется)

```bash
# Удалить все миграции
cd wb_bot
alembic downgrade base

# Применить миграции заново
alembic upgrade head
```

### Вариант 2: Через psql

```bash
# Подключитесь к PostgreSQL
psql $DATABASE_URL

# Удалите базу данных
DROP DATABASE IF EXISTS wb_bot_db;

# Создайте заново
CREATE DATABASE wb_bot_db;

# Выйдите из psql
\q

# Примените миграции
cd wb_bot
alembic upgrade head
```

## 🧹 Очистка файлов пользователей

### Очистка только файлов (без БД)

```bash
python clear_user_files.py
```

Вам будет предложено ввести `YES` для подтверждения.

Это удалит:
- ✅ Папки `wb_user_data_*` (данные браузеров)
- ✅ Файлы `wb_cookies_*.json` (cookies)
- ✅ Папки `screenshots_*` (скриншоты)

### Ручная очистка файлов

#### Windows (PowerShell):

```powershell
# Удалить папки данных браузеров
Remove-Item -Recurse -Force wb_user_data_*

# Удалить файлы cookies
Remove-Item -Force wb_cookies_*.json

# Удалить скриншоты
Remove-Item -Recurse -Force screenshots_*
```

#### Linux/Mac:

```bash
# Удалить все файлы пользователей
rm -rf wb_user_data_* wb_cookies_*.json screenshots_*
```

## 📊 Проверка базы данных

### Проверить количество записей:

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

### Проверить подключение к БД:

```bash
python -c "
import asyncio
from wb_bot.app.database import init_database, health_check, close_database

async def test():
    await init_database()
    if await health_check():
        print('✅ База данных доступна')
    else:
        print('❌ База данных недоступна')
    await close_database()

asyncio.run(test())
"
```

## 🔐 Безопасность

### Создание резервной копии перед очисткой:

```bash
# PostgreSQL backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление из backup
psql $DATABASE_URL < backup_20250102_120000.sql
```

## ⚠️ Важные замечания

1. **Всегда делайте backup перед очисткой продакшн БД!**
2. **Очистка БД не влияет на структуру таблиц** (они остаются)
3. **После очистки пользователи должны заново:** 
   - Добавить API ключи
   - Настроить мониторинг
   - Авторизоваться в браузере (если используется браузерное бронирование)
4. **Файлы браузеров не удаляются автоматически** - очистите их вручную если нужно

## 🚀 Быстрые команды

### Основные команды:

```bash
# 🔥 ПОЛНАЯ очистка всего (БД + файлы) - РЕКОМЕНДУЕТСЯ
python clear_all.py

# 🗑️ Очистить только БД
python clear_database.py

# 🧹 Очистить только файлы пользователей
python clear_user_files.py
```

### Альтернативные команды:

```bash
# Очистить файлы вручную (Windows)
Remove-Item -Recurse -Force wb_user_data_*,wb_cookies_*.json,screenshots_*

# Очистить файлы вручную (Linux/Mac)
rm -rf wb_user_data_* wb_cookies_*.json screenshots_*
```

## 📝 Логи

Все операции очистки логируются в консоль и показывают:
- Сколько записей было в каждой таблице
- Какие таблицы были очищены
- Общее количество удаленных записей

Пример вывода:
```
============================================================
📊 СТАТИСТИКА ОЧИСТКИ:
============================================================
   booking_results              :     42 записей
   booking_tasks                :     15 записей
   monitoring_tasks             :      8 записей
   api_keys                     :      3 записей
   browser_sessions             :      2 записей
   users                        :      2 записей
============================================================
   ВСЕГО УДАЛЕНО                :     72 записей
============================================================
```

