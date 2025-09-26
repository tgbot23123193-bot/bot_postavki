# 🚀 Запуск браузера пользователя без бота

Документация по запуску браузера конкретного пользователя для ручной работы.

## 📋 Доступные скрипты

### 1. 🔧 Базовый запуск - `launch_browser.py`

**Простой запуск браузера пользователя:**

```bash
# Базовая команда
python launch_browser.py USER_ID

# Примеры
python launch_browser.py 123456789
python launch_browser.py 5123262366
```

**Что делает:**
- ✅ Запускает браузер с профилем пользователя
- ✅ Загружает все сохраненные куки и данные авторизации
- ✅ Открывает браузер в видимом режиме (не headless)
- ✅ Ждет до нажатия Ctrl+C для завершения

### 2. 🎮 Расширенный запуск - `launch_browser_advanced.py`

**Запуск с дополнительными функциями:**

```bash
# Базовый запуск
python launch_browser_advanced.py USER_ID

# С дополнительными опциями
python launch_browser_advanced.py USER_ID --headless
python launch_browser_advanced.py USER_ID --interactive
python launch_browser_advanced.py USER_ID --open-redistribution
python launch_browser_advanced.py USER_ID --get-warehouses

# Комбинирование опций
python launch_browser_advanced.py 123456789 --interactive --open-redistribution
```

**Опции:**
- `--headless` - Запуск в невидимом режиме
- `--interactive` - Интерактивный режим с командами
- `--open-redistribution` - Сразу открыть страницу перераспределения
- `--get-warehouses` - Получить список доступных складов

### 3. 🖱️ Быстрый запуск через скрипты

**Windows:**
```cmd
launch.bat 123456789
```

**Linux/Mac:**
```bash
./launch.sh 123456789
```

## 🎮 Интерактивный режим

В интерактивном режиме доступны команды:

```bash
python launch_browser_advanced.py 123456789 --interactive
```

**Доступные команды:**
- `open` - Открыть страницу перераспределения
- `warehouses` - Получить список складов
- `url` - Показать текущий URL
- `screenshot` - Сделать скриншот
- `goto <url>` - Перейти на URL
- `help` - Показать справку
- `quit` - Выход

**Пример сеанса:**
```
🔸 Введите команду: open
✅ Страница перераспределения открыта

🔸 Введите команду: warehouses
✅ Найдено складов: 3
  1. Краснодар
  2. Электросталь
  3. Москва

🔸 Введите команду: screenshot
📸 Скриншот сохранен: screenshots_123456789/manual_screenshot.png

🔸 Введите команду: quit
```

## 📁 Структура профилей

Каждый пользователь имеет свой профиль браузера:

```
wb_user_data_USER_ID/
├── cookies.json          # Сохраненные куки
├── local_storage.json    # Данные localStorage
├── session_storage.json  # Данные sessionStorage
└── Default/              # Профиль Chromium
    ├── Cookies
    ├── Local Storage/
    └── Session Storage/
```

## 🎯 Примеры использования

### Запуск для работы с WB

```bash
# 1. Запускаем браузер пользователя
python launch_browser.py 123456789

# 2. Или с автоматическим открытием страницы перераспределения
python launch_browser_advanced.py 123456789 --open-redistribution

# 3. Или в интерактивном режиме для полного контроля
python launch_browser_advanced.py 123456789 --interactive
```

### Отладка и тестирование

```bash
# Получить список складов без открытия браузера
python launch_browser_advanced.py 123456789 --headless --get-warehouses

# Сделать скриншот текущего состояния
python launch_browser_advanced.py 123456789 --interactive
# Затем в интерактивном режиме: screenshot
```

### Проверка авторизации

```bash
# Запускаем браузер и проверяем URL
python launch_browser_advanced.py 123456789 --interactive
# В интерактивном режиме:
# url - показать текущий URL
# goto https://seller.wildberries.ru - перейти на страницу продавца
```

## 🔒 Безопасность

**Важные моменты:**
- ✅ Все данные авторизации сохраняются в профиле пользователя
- ✅ Каждый пользователь имеет изолированный профиль
- ✅ Куки и сессии не пересекаются между пользователями
- ⚠️ Не запускайте скрипт от имени администратора без необходимости
- ⚠️ Убедитесь, что USER_ID принадлежит авторизованному пользователю

## 🐛 Устранение неполадок

### Ошибка "Браузер не запущен"
```bash
# Проверьте, что USER_ID существует в базе данных
python -c "from app.services.database_service import db_service; import asyncio; asyncio.run(db_service.get_user(123456789))"
```

### Ошибка "Страница не доступна"
```bash
# Перезапустите браузер
python launch_browser.py 123456789
```

### Проблемы с авторизацией
```bash
# Запустите браузер и авторизуйтесь заново
python launch_browser.py 123456789
# Перейдите на seller.wildberries.ru и войдите в аккаунт
```

## 💡 Полезные команды

```bash
# Список всех пользователей в базе
python -c "from app.services.database_service import db_service; import asyncio; asyncio.run(db_service.get_all_users())"

# Проверка статуса браузерной сессии пользователя
python -c "from app.services.database_service import db_service; import asyncio; print(asyncio.run(db_service.get_browser_session(123456789)))"

# Очистка профиля пользователя (ОСТОРОЖНО!)
# rm -rf wb_user_data_123456789/
```


