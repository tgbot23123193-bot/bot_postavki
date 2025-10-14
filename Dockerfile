# ═══════════════════════════════════════════════════════════════
# 🚀 RAILWAY OPTIMIZED DOCKERFILE WITH PLAYWRIGHT
# ═══════════════════════════════════════════════════════════════
# Этот Dockerfile оптимизирован для Railway с полной поддержкой Playwright
# ═══════════════════════════════════════════════════════════════

FROM python:3.11-slim

# Установка системных зависимостей и Playwright зависимостей
RUN apt-get update && apt-get install -y \
    # Build dependencies
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    # Runtime dependencies
    curl \
    ca-certificates \
    wget \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    # Additional libraries
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Установка Playwright браузеров (chromium + firefox)
RUN playwright install chromium firefox && \
    playwright install-deps chromium && \
    playwright install-deps firefox

# Копирование исходного кода
COPY . .

# Создание директорий для данных пользователей
RUN mkdir -p /app/user_data && \
    chmod 755 /app/user_data

# Переменные окружения для Railway
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Порт для Railway webhook
EXPOSE 8080

# Команда запуска
CMD ["python", "-m", "wb_bot.app.main"]
