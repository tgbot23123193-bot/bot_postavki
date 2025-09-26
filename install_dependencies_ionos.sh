#!/bin/bash

# Complete Installation Script for Ionos Ubuntu

set -e

echo "🚀 Полная установка WB Bot на Ionos Ubuntu..."

# Проверяем что мы в правильной директории
if [ ! -f "requirements.txt" ]; then
    echo "❌ Не найдены файлы проекта. Убедитесь что находитесь в корне проекта."
    exit 1
fi

# Обновляем систему
echo "📦 Обновляем систему..."
sudo apt update && sudo apt upgrade -y

# Устанавливаем базовые зависимости
echo "🔧 Устанавливаем базовые зависимости..."
sudo apt install -y \
    python3.11 \
    python3.11-pip \
    python3.11-venv \
    postgresql \
    postgresql-contrib \
    redis-server \
    nodejs \
    npm \
    curl \
    wget \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    htop \
    nano

# Устанавливаем Node.js (для Playwright)
echo "📦 Устанавливаем Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Настраиваем PostgreSQL
echo "🗄️ Настраиваем PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создаем базу данных и пользователя
DB_PASSWORD=$(openssl rand -base64 32)
echo "🔐 Пароль для БД: $DB_PASSWORD"

sudo -u postgres psql -c "CREATE USER wb_bot_user WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE wb_bot_prod OWNER wb_bot_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wb_bot_prod TO wb_bot_user;"

# Настраиваем Redis
echo "🔄 Настраиваем Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Создаем пользователя для бота
echo "👤 Создаем пользователя..."
sudo useradd --create-home --shell /bin/bash wb_bot_user || true
sudo mkdir -p /home/wb_bot_user
sudo chown -R wb_bot_user:wb_bot_user /home/wb_bot_user

# Копируем файлы проекта
echo "📁 Копируем файлы проекта..."
sudo cp -r . /home/wb_bot_user/bot_postavki/
sudo chown -R wb_bot_user:wb_bot_user /home/wb_bot_user/bot_postavki

# Устанавливаем зависимости как пользователь бота
echo "🐍 Устанавливаем Python зависимости..."
cd /home/wb_bot_user/bot_postavki

# Создаем виртуальное окружение
sudo -u wb_bot_user python3.11 -m venv venv

# Активируем окружение и устанавливаем зависимости
sudo -u wb_bot_user bash -c "source venv/bin/activate && pip install --upgrade pip"
sudo -u wb_bot_user bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Устанавливаем Playwright
echo "🎭 Устанавливаем Playwright браузеры..."
sudo -u wb_bot_user bash -c "source venv/bin/activate && playwright install chromium"
sudo -u wb_bot_user bash -c "source venv/bin/activate && playwright install-deps"

# Обновляем .env файл с правильными данными
echo "⚙️ Обновляем конфигурацию..."
sudo -u wb_bot_user bash -c "cd /home/wb_bot_user/bot_postavki && cp config_ionos.env .env"

# Заменяем плейсхолдеры в .env
sed -i "s/postgresql:\/\/username:password@localhost:5432\/wb_bot_prod/postgresql:\/\/wb_bot_user:$DB_PASSWORD@localhost:5432\/wb_bot_prod/g" /home/wb_bot_user/bot_postavki/.env
sed -i "s/redis:\/\/:your_secure_redis_password_here@localhost:6379\/0/redis:\/\/localhost:6379\/0/g" /home/wb_bot_user/bot_postavki/.env

# Применяем миграции
echo "🗄️ Применяем миграции базы данных..."
sudo -u wb_bot_user bash -c "source venv/bin/activate && alembic upgrade head"

# Создаем systemd службу
echo "⚙️ Создаем systemd службу..."
sudo tee /etc/systemd/system/wb-bot.service > /dev/null <<EOF
[Unit]
Description=WB Auto-Booking Bot
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=wb_bot_user
Group=wb_bot_user
WorkingDirectory=/home/wb_bot_user/bot_postavki
EnvironmentFile=/home/wb_bot_user/bot_postavki/.env
ExecStart=/home/wb_bot_user/bot_postavki/venv/bin/python -m wb_bot.app.main
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/home/wb_bot_user/bot_postavki/wb_user_data

[Install]
WantedBy=multi-user.target
EOF

# Запускаем службу
echo "🚀 Запускаем службу бота..."
sudo systemctl daemon-reload
sudo systemctl enable wb-bot.service
sudo systemctl start wb-bot.service

# Проверяем статус
echo "🔍 Проверяем статус развертывания..."
sudo systemctl status wb-bot.service --no-pager -l

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Обновите .env файл с реальными данными:"
echo "   - TG_BOT_TOKEN от BotFather"
echo "   - TG_WEBHOOK_URL (если используете)"
echo "   - SECURITY_ENCRYPTION_KEY и SECURITY_JWT_SECRET"
echo "2. Перезапустите бота: sudo systemctl restart wb-bot.service"
echo "3. Проверьте логи: sudo journalctl -u wb-bot.service -f"
echo "4. Убедитесь что бот отвечает в Telegram"
echo ""
echo "💾 Важная информация:"
echo "База данных: wb_bot_prod"
echo "Пользователь: wb_bot_user"
echo "Пароль: $DB_PASSWORD"
echo "Сохраните пароль в безопасном месте!"
