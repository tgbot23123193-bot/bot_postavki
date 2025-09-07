# ТЕХНИЧЕСКОЕ ЗАДАНИЕ ДЛЯ CURSOR AI
## Wildberries Auto-Booking & Redistribution Telegram Bot

**КОНТЕКСТ:** Вы - опытный Python разработчик с 10+ летним стажем, специализирующийся на создании высоконагруженных Telegram ботов и интеграции с внешними API. Ваша задача - создать промышленный код с идеальной архитектурой с первого раза.

---

## АРХИТЕКТУРНЫЕ ТРЕБОВАНИЯ

### Технический стек:
- **Python 3.11+**
- **aiogram 3.x** (асинхронный Telegram Bot framework)
- **SQLAlchemy 2.0** с **asyncpg** (PostgreSQL async driver)
- **Redis** для кэширования и очередей задач
- **Celery** для фоновых задач мониторинга
- **Pydantic** для валидации данных
- **aiohttp** для HTTP клиента
- **cryptography** для шифрования API ключей

### Структура проекта:
```
wb_bot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Точка входа
│   ├── config.py              # Конфигурация
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy модели
│   │   ├── connection.py      # Подключение к БД
│   │   └── migrations/        # Alembic миграции
│   ├── api/
│   │   ├── __init__.py
│   │   ├── wb_client.py       # WB API клиент
│   │   └── schemas.py         # Pydantic схемы
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers/          # Обработчики команд
│   │   ├── keyboards/         # Inline клавиатуры
│   │   ├── middlewares/       # Middleware для бота
│   │   └── states.py          # FSM состояния
│   ├── services/
│   │   ├── __init__.py
│   │   ├── monitoring.py      # Мониторинг слотов
│   │   ├── booking.py         # Логика бронирования
│   │   ├── redistribution.py  # Перераспределение
│   │   └── auth.py            # Работа с API ключами
│   └── utils/
│       ├── __init__.py
│       ├── encryption.py      # Шифрование данных
│       ├── logger.py          # Настройка логирования
│       └── decorators.py      # Декораторы
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── alembic.ini
```

---

## ДЕТАЛЬНЫЕ ФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

### 1. СИСТЕМА МОНИТОРИНГА (КРИТИЧНО!)

**Требования к производительности:**
- Частота проверки: **1 секунда** на каждый активный мониторинг
- Асинхронная обработка до 1000+ одновременных запросов
- Retry-механизм с экспоненциальным backoff
- Circuit breaker для защиты от rate limiting

**Архитектура мониторинга:**
```python
class SlotMonitor:
    """
    Высокопроизводительный мониторинг слотов поставок WB
    - Использует aiohttp ClientSession с connection pooling
    - Асинхронная обработка через asyncio.gather()
    - Кэширование результатов в Redis (TTL: 5 сек)
    - Интеллектуальное распределение нагрузки по API ключам
    """
```

### 2. ПОЛЬЗОВАТЕЛЬСКИЙ ИНТЕРФЕЙС

**Календарь дат (ОБЯЗАТЕЛЬНО!):**
- Inline keyboard с навигацией по месяцам
- Выбор начальной и конечной даты через кнопки
- Визуальное отображение выбранного диапазона
- Валидация: конечная дата >= начальной

**Пример реализации:**
```python
class DateRangeCalendar:
    """
    Интерактивный календарь для выбора диапазона дат
    - Состояния: выбор начальной даты -> выбор конечной даты
    - Callback data: "cal:{action}:{year}:{month}:{day}"
    - Поддержка навигации: назад/вперед по месяцам
    """
```

### 3. БАЗА ДАННЫХ

**Модели SQLAlchemy:**

```python
class User(Base):
    __tablename__ = 'users'
    
    id: int = Column(BigInteger, primary_key=True)  # Telegram user_id
    username: str = Column(String(255), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    is_active: bool = Column(Boolean, default=True)
    trial_bookings: int = Column(Integer, default=0)  # Счетчик пробных бронирований
    
    # Отношения
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    monitoring_tasks = relationship("MonitoringTask", back_populates="user")

class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: int = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    encrypted_key: str = Column(String(500), nullable=False)  # Зашифрованный API ключ
    name: str = Column(String(100), nullable=True)  # Название для ключа
    is_valid: bool = Column(Boolean, default=True)
    last_used: datetime = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

class MonitoringTask(Base):
    __tablename__ = 'monitoring_tasks'
    
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: int = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    warehouse_id: int = Column(Integer, nullable=False)
    warehouse_name: str = Column(String(100), nullable=False)
    date_from: date = Column(Date, nullable=False)
    date_to: date = Column(Date, nullable=False)
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    # Результаты мониторинга
    bookings = relationship("BookingResult", back_populates="task")

class BookingResult(Base):
    __tablename__ = 'booking_results'
    
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    task_id: int = Column(Integer, ForeignKey('monitoring_tasks.id'), nullable=False)
    booking_date: date = Column(Date, nullable=False)
    slot_time: str = Column(String(50), nullable=True)  # Время слота
    wb_booking_id: str = Column(String(100), nullable=True)  # ID брони в WB
    status: str = Column(String(50), default='pending')  # pending, confirmed, cancelled
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
```

### 4. WILDBERRIES API ИНТЕГРАЦИЯ

**HTTP клиент с полной обработкой ошибок:**

```python
class WBAPIClient:
    """
    Профессиональный клиент для работы с WB API
    
    Возможности:
    - Connection pooling (aiohttp.ClientSession)
    - Автоматический retry с exponential backoff
    - Rate limiting protection (429 ошибки)
    - Валидация API ключей через тестовый запрос
    - Логирование всех запросов и ответов
    - Обработка всех HTTP статус кодов
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://suppliers-api.wildberries.ru"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    async def get_available_slots(self, warehouse_id: int, date_from: str, date_to: str):
        """Получение доступных слотов для поставок"""
        
    async def create_booking(self, warehouse_id: int, booking_date: str, slot_time: str):
        """Создание брони поставки"""
        
    async def get_redistribution_limits(self):
        """Получение лимитов перераспределения"""
        
    async def create_redistribution_request(self, items: list, target_warehouse: int):
        """Создание заявки на перераспределение"""
```

### 5. СИСТЕМА БЕЗОПАСНОСТИ

**Шифрование API ключей:**
```python
class EncryptionService:
    """
    AES-256 шифрование для API ключей WB
    - Уникальный salt для каждого ключа
    - Безопасное хранение master key в environment
    - Автоматическое тестирование ключей при добавлении
    """
```

**Валидация и ограничения:**
- Максимум 5 API ключей на пользователя
- Тестирование ключа при добавлении (проверочный запрос к WB API)
- Деактивация неработающих ключей
- Ротация ключей при ошибках авторизации

### 6. СИСТЕМА УВЕДОМЛЕНИЙ

**Форматы сообщений:**
```python
BOOKING_SUCCESS = """
🎉 ПОСТАВКА ПОЙМАНА!

📦 Склад: {warehouse_name}
📅 Дата: {booking_date}
⏰ Время: {slot_time}
🔑 API ключ: {key_name}

Детали брони: #{booking_id}
"""

REDISTRIBUTION_SUCCESS = """
📦 ПЕРЕРАСПРЕДЕЛЕНИЕ ВЫПОЛНЕНО!

🏪 Со склада: {from_warehouse}
🏪 На склад: {to_warehouse}
📊 Товаров: {items_count} шт.
💼 Заявка: #{request_id}
"""
```

### 7. ПРОБНЫЙ ПЕРИОД И МОНЕТИЗАЦИЯ

**Логика пробного периода:**
- 2 бесплатные поймаСТВкИ для нового пользователя
- Счетчик в БД: `User.trial_bookings`
- После исчерпания - блокировка с предложением оплаты
- История операций для аналитики

---

## КРИТИЧНЫЕ ОСОБЕННОСТИ РЕАЛИЗАЦИИ

### Асинхронность везде:
- Все операции с БД через async/await
- HTTP запросы через aiohttp
- Фоновые задачи через asyncio.create_task()

### Обработка ошибок:
- try/except для всех внешних вызовов  
- Логирование всех исключений
- Graceful degradation при недоступности сервисов
- Уведомления пользователей об ошибках

### Мониторинг производительности:
- Метрики времени выполнения запросов
- Статистика успешности бронирований  
- Мониторинг нагрузки на API ключи

### Масштабируемость:
- Возможность горизонтального масштабирования
- Stateless архитектура
- Использование Redis для shared state

---

## ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ

1. **Логирование:** Structured logging с JSON форматом
2. **Конфигурация:** Через environment variables + .env файл
3. **Тестирование:** Unit tests для критичной логики
4. **Документация:** Docstrings для всех публичных методов
5. **Типизация:** Type hints везде где возможно

**ВАЖНО:** Код должен быть готов к production развертыванию с первого раза. Никаких TODO, заглушек или временных решений!