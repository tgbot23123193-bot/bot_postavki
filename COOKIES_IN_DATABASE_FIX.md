# ✅ Изоляция браузерных сессий - Cookies в БД

## 🎯 Проблема

Пользователь сообщил: **"почему он говорит что я вошел в аккаунт если я не входил"**

### Причина:
- Cookies хранились в локальных файлах `wb_cookies_{user_id}.json`
- Могла происходить путаница между пользователями
- Cookies не были полностью изолированы в БД
- При проверке авторизации могли загружаться чужие cookies из кеша

## ✅ Решение

### 1. Добавлено поле `cookies_data` в таблицу `browser_sessions`

**Миграция:** `20251003_1127_8346b614344c_add_cookies_data_to_browser_sessions.py`

```python
def upgrade() -> None:
    """Upgrade database schema."""
    # Добавляем поле cookies_data для хранения cookies в БД как JSON
    op.add_column('browser_sessions', sa.Column('cookies_data', sa.Text(), nullable=True))
```

**Модель:** `wb_bot/app/database/models.py`

```python
class BrowserSession(Base):
    ...
    cookies_file = Column(String(500), nullable=True)  # Устаревшее (для обратной совместимости)
    cookies_data = Column(Text, nullable=True)  # ✅ НОВОЕ - JSON с cookies
```

### 2. Добавлены функции в `database_service.py`

#### Сохранение cookies:
```python
async def save_browser_cookies(self, user_id: int, cookies_json: str) -> bool:
    """Сохранить cookies в БД для пользователя."""
    # Сохраняет cookies как JSON текст в поле cookies_data
    # Привязано к конкретному user_id
```

#### Загрузка cookies:
```python
async def load_browser_cookies(self, user_id: int) -> Optional[str]:
    """Загрузить cookies из БД для пользователя."""
    # Загружает cookies ТОЛЬКО для конкретного user_id
    # Возвращает JSON текст или None
```

### 3. Переписаны функции в `browser_automation.py`

#### До (старая версия):
```python
async def _load_cookies(self):
    """Загружает cookies из файлов."""
    # ❌ Загружало из локальных файлов
    # ❌ Могло загрузить чужие cookies
    if self.cookies_file.exists():
        with open(self.cookies_file, 'r') as f:
            cookies = json.load(f)
```

#### После (новая версия):
```python
async def _load_cookies(self):
    """ЗАГРУЖАЕМ КУКИ ТОЛЬКО ИЗ БД ДЛЯ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ."""
    if self.user_id:
        # ✅ Загружает ТОЛЬКО из БД
        # ✅ Только для конкретного user_id
        cookies_json = await db_service.load_browser_cookies(self.user_id)
        if cookies_json:
            cookies = json.loads(cookies_json)
            await self.context.add_cookies(cookies)
            logger.info(f"🍪 Куки загружены из БД для пользователя {self.user_id}")
```

#### Сохранение cookies (новая версия):
```python
async def _save_cookies(self):
    """СОХРАНЯЕМ КУКИ ТОЛЬКО В БД ДЛЯ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ."""
    if not self.user_id:
        return
        
    cookies = await self.context.cookies()
    cookies_json = json.dumps(cookies, ensure_ascii=False)
    
    # ✅ Сохраняет ТОЛЬКО в БД
    # ✅ Привязано к user_id
    await db_service.save_browser_cookies(self.user_id, cookies_json)
    logger.info(f"💾 Куки сохранены в БД для пользователя {self.user_id}")
```

### 4. Улучшена проверка авторизации `should_skip_login()`

#### Новая логика:

```python
async def should_skip_login(self) -> bool:
    """Проверяет нужно ли пропустить авторизацию (если есть валидная сессия с cookies)."""
    
    # ШАГ 1: Проверяем наличие cookies в БД для ЭТОГО пользователя
    cookies_json = await db_service.load_browser_cookies(self.user_id)
    if not cookies_json:
        logger.info(f"📭 Нет сохраненных cookies для пользователя {self.user_id}")
        return False  # ❌ Нет cookies → требуется авторизация
    
    # ШАГ 2: Проверяем валидность cookies на WB
    await self.page.goto(
        "https://seller.wildberries.ru/supplies-management/all-supplies", 
        wait_until="networkidle"
    )
    
    current_url = self.page.url
    
    # ШАГ 3: Проверяем редирект
    if 'seller-auth.wildberries.ru' in current_url:
        # ❌ Редирект на логин → cookies устарели
        logger.info(f"❌ Cookies устарели для пользователя {self.user_id}")
        await db_service.update_browser_session_valid(self.user_id, False)
        return False
    
    if 'seller.wildberries.ru' in current_url:
        # ✅ Остались на seller → cookies валидны
        logger.info(f"✅ Пользователь {self.user_id} АВТОРИЗОВАН!")
        await db_service.update_browser_session_valid(self.user_id, True)
        return True
```

#### Преимущества новой проверки:
1. ✅ Проверяет наличие cookies ДО попытки перехода
2. ✅ Использует правильный URL (`seller-auth.wildberries.ru`)
3. ✅ Проверяет реальный редирект, а не предполагает
4. ✅ Синхронизирует статус с БД
5. ✅ Не помечает сессию валидной если cookies устарели

## 📊 Структура данных в БД

### Таблица `browser_sessions`:
```
user_id: 1259602460
phone_number: "+79618500085"
session_valid: true
cookies_data: '[{"name":"session_id","value":"abc123",...},{"name":"auth_token",...}]'
last_login_check: 2025-10-03 11:30:00
last_successful_login: 2025-10-03 11:25:00
```

### Изоляция:
- ✅ Каждый `user_id` имеет свою запись в `browser_sessions`
- ✅ Cookies хранятся в поле `cookies_data` как JSON текст
- ✅ При загрузке выбирается `WHERE user_id = {user_id}`
- ✅ Нет возможности загрузить чужие cookies

## 🔄 Полный цикл работы

### 1. Первая авторизация (нет cookies):

```
Пользователь A (ID: 123):
1. should_skip_login() → cookies_json = None → False (требуется авторизация)
2. Ввод телефона и SMS кода
3. _save_cookies() → сохраняет в БД: user_id=123, cookies_data='[...]'
4. update_browser_session_valid(123, True) → session_valid=True
```

### 2. Повторный запуск (есть cookies):

```
Пользователь A (ID: 123):
1. should_skip_login() → cookies_json = '[...]' (найдены в БД)
2. Загружает cookies в браузер
3. Переход на seller.wildberries.ru/supplies-management
4. Проверка URL: 'seller.wildberries.ru' → ✅ Авторизован
5. Возврат True → пропускает авторизацию
```

### 3. Другой пользователь (свои cookies):

```
Пользователь B (ID: 456):
1. should_skip_login() → SELECT WHERE user_id=456 → cookies_json = None
2. Требуется авторизация
3. Ввод своих данных
4. _save_cookies() → сохраняет в БД: user_id=456, cookies_data='[другие cookies]'
```

### 4. Устаревшие cookies:

```
Пользователь A (ID: 123):
1. should_skip_login() → cookies_json = '[старые cookies]'
2. Загружает cookies в браузер
3. Переход на seller.wildberries.ru/supplies-management
4. Редирект на 'seller-auth.wildberries.ru' → ❌ Cookies устарели
5. update_browser_session_valid(123, False)
6. Возврат False → требуется авторизация
7. После успешного входа: новые cookies сохраняются в БД
```

## 🎯 Что это решает

### ✅ Изоляция пользователей:
- Каждый пользователь имеет свои cookies в БД
- Невозможно загрузить чужие cookies
- Нет конфликтов между сессиями

### ✅ Правильная проверка авторизации:
- Проверка наличия cookies ДО попытки использования
- Реальная проверка валидности через редирект
- Синхронизация статуса с БД

### ✅ Актуальность данных:
- Cookies автоматически обновляются в БД
- Устаревшие cookies не используются
- Автоматическая инвалидация при редиректе на логин

### ✅ Безопасность:
- Cookies хранятся в БД, а не в файлах
- Привязка к user_id на уровне БД
- Невозможна подмена сессии

## 🚀 Применение

```powershell
# Остановить бота
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process -Force

# Запустить с новой изоляцией
cd wb_bot
python -m app.main
```

## 📝 Логирование

### При загрузке cookies:
```
🍪 Куки загружены из БД для пользователя 1259602460
```

### При отсутствии cookies:
```
📭 Нет сохраненных cookies для пользователя 1259602460 - требуется авторизация
```

### При сохранении cookies:
```
💾 Куки сохранены в БД для пользователя 1259602460
```

### При проверке авторизации:
```
🔍 Проверяю необходимость авторизации для пользователя 1259602460
🌐 Проверяю валидность cookies на странице WB...
📍 Текущий URL: https://seller.wildberries.ru/supplies-management/all-supplies
✅ Пользователь 1259602460 АВТОРИЗОВАН! Cookies валидны.
```

### При устаревших cookies:
```
🔍 Проверяю необходимость авторизации для пользователя 1259602460
🌐 Проверяю валидность cookies на странице WB...
📍 Текущий URL: https://seller-auth.wildberries.ru/ru/?redirect_url=...
❌ Cookies устарели для пользователя 1259602460 (редирект на логин)
```

## ✅ ИТОГО

### Изменено:
1. ✅ Добавлено поле `cookies_data` в таблицу `browser_sessions`
2. ✅ Добавлены функции `save_browser_cookies()` и `load_browser_cookies()` в `database_service.py`
3. ✅ Переписаны `_load_cookies()` и `_save_cookies()` в `browser_automation.py`
4. ✅ Улучшена `should_skip_login()` с правильной проверкой валидности

### Результат:
- ✅ **Полная изоляция cookies между пользователями**
- ✅ **Правильная проверка авторизации**
- ✅ **Хранение в БД, а не в файлах**
- ✅ **Невозможность путаницы между сессиями**

---

**Теперь каждый пользователь имеет ПОЛНОСТЬЮ ИЗОЛИРОВАННУЮ браузерную сессию в БД!** 🎉🔐


