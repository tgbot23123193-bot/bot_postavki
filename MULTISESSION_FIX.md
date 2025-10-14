# Исправление мультисессии

## Проблема
Мультисессия не работала, потому что разные части кода использовали **разные экземпляры** `BrowserManager`:
- В `main.py` создавался новый экземпляр: `self.browser_manager = BrowserManager()`
- В `browser_manager.py` был глобальный экземпляр: `browser_manager = BrowserManager()`
- В `redistribution.py` в функции `stop_redistribution_hunt` создавался еще один новый экземпляр

Это приводило к тому, что браузеры разных пользователей не изолировались друг от друга, так как словари `_browsers` находились в разных экземплярах менеджера.

## Решение
Теперь **все части кода используют ОДИН глобальный экземпляр** `browser_manager` из модуля `browser_manager.py`:

### Изменения:

#### 1. `wb_bot/app/main.py`
```python
# БЫЛО:
from .services.browser_manager import BrowserManager
self.browser_manager = BrowserManager()

# СТАЛО:
from .services.browser_manager import browser_manager  # Глобальный экземпляр
self.browser_manager = browser_manager
```

#### 2. `wb_bot/app/bot/handlers/redistribution.py`
```python
# БЫЛО (строка 1319):
browser_manager = BrowserManager()
await browser_manager.close_browser(user_id)

# СТАЛО:
# Используем глобальный browser_manager
if browser_manager:
    await browser_manager.close_browser(user_id)
```

## Как работает мультисессия

### Архитектура изоляции

1. **BrowserManager** хранит словарь браузеров:
   ```python
   self._browsers: Dict[int, WBBrowserAutomationPro] = {}  # user_id -> browser_instance
   ```

2. **Каждый пользователь получает уникальный браузер** с:
   - Уникальным портом: `9222 + hash(user_id) % 1000` (порты 9222-10221)
   - Уникальными папками: `wb_user_data_{user_id}`, `screenshots_{user_id}`
   - Уникальным файлом cookies: `wb_cookies_{user_id}.json`

3. **Повторное использование браузеров**:
   - Если браузер пользователя уже существует и активен - переиспользуется
   - Если браузер закрыт или умер - создается новый

### Пример работы

```python
# Пользователь 1 (ID: 123456789)
browser1 = await browser_manager.get_browser(user_id=123456789)
# Создает: порт 9222, папка wb_user_data_123456789

# Пользователь 2 (ID: 987654321)  
browser2 = await browser_manager.get_browser(user_id=987654321)
# Создает: порт 9485, папка wb_user_data_987654321

# Браузеры полностью изолированы друг от друга!
```

## Тестирование

Теперь можно запустить бота и протестировать мультисессию:

```bash
cd wb_bot
python -m app.main
```

**Что нужно проверить:**
1. ✅ Несколько пользователей могут одновременно работать с ботом
2. ✅ Каждый пользователь видит только свои данные
3. ✅ Браузеры не конфликтуют друг с другом
4. ✅ Каждый пользователь может остановить свою охоту независимо

## Дополнительные улучшения

Система также поддерживает:
- 🔒 Thread-safe доступ к браузерам через `asyncio.Lock()`
- 🧹 Автоматическая очистка неактивных браузеров
- 🎭 Клонирование сессий для мультибронирования
- 📊 Отслеживание активных пользователей

## Структура файлов пользователей

После запуска бота каждый пользователь будет иметь:
```
project_root/
├── wb_user_data_123456789/     # Данные браузера пользователя 1
├── wb_user_data_987654321/     # Данные браузера пользователя 2
├── wb_cookies_123456789.json   # Cookies пользователя 1
├── wb_cookies_987654321.json   # Cookies пользователя 2
├── screenshots_123456789/      # Скриншоты пользователя 1
└── screenshots_987654321/      # Скриншоты пользователя 2
```

## Критические точки

⚠️ **НИКОГДА НЕ СОЗДАВАЙТЕ НОВЫЙ ЭКЗЕМПЛЯР BrowserManager!**

Всегда импортируйте глобальный:
```python
# ПРАВИЛЬНО ✅
from ...services.browser_manager import browser_manager

# НЕПРАВИЛЬНО ❌
from ...services.browser_manager import BrowserManager
manager = BrowserManager()  # Это создаст отдельный менеджер!
```


