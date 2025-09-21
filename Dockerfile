# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as base

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Установка Playwright браузеров
RUN playwright install chromium && \
    playwright install-deps chromium

# Production stage
FROM python:3.11-slim as production

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для запуска приложения
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Копирование установленных пакетов из base stage
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin
COPY --from=base /root/.cache/ms-playwright /root/.cache/ms-playwright

# Копирование исходного кода
COPY . .

# Установка прав доступа
RUN chown -R appuser:appuser /app

# Переключение на непривилегированного пользователя
USER appuser

# Переменные окружения для Railway
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Порт для Railway (если нужен webhook)
EXPOSE 8080

# Health check убран для стабильности деплоя

# Команда запуска
CMD ["python", "-m", "wb_bot.app.main"]
