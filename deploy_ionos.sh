#!/bin/bash

# Ionos Ubuntu Deployment Script
# Выполните этот скрипт на вашем Ionos сервере

set -e

echo "🚀 Начинаем развертывание WB Bot на Ionos Ubuntu..."

# Обновляем систему
echo "📦 Обновляем систему..."
sudo apt update && sudo apt upgrade -y

# Устанавливаем необходимые пакеты
echo "🔧 Устанавливаем системные зависимости..."
sudo apt install -y \
    python3.11 \
    python3.11-pip \
    python3.11-venv \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    certbot \
    python3-certbot-nginx \
    curl \
    wget \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev

# Устанавливаем Node.js для Playwright
echo "📦 Устанавливаем Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Настраиваем PostgreSQL
echo "🗄️ Настраиваем PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создаем базу данных и пользователя
sudo -u postgres psql -c "CREATE USER wb_bot_user WITH PASSWORD 'your_secure_password_here';"
sudo -u postgres psql -c "CREATE DATABASE wb_bot_prod OWNER wb_bot_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wb_bot_prod TO wb_bot_user;"

# Настраиваем Redis
echo "🔄 Настраиваем Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Настраиваем firewall
echo "🔥 Настраиваем firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# Клонируем репозиторий (если нужно)
if [ ! -d "wb_bot" ]; then
    echo "📥 Клонируем репозиторий..."
    git clone https://github.com/your-repo/bot_postavki.git
    cd bot_postavki
fi

# Создаем виртуальное окружение
echo "🐍 Создаем виртуальное окружение..."
python3.11 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
echo "📦 Устанавливаем Python зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

# Устанавливаем Playwright
echo "🎭 Устанавливаем Playwright браузеры..."
playwright install chromium
playwright install-deps

# Применяем миграции базы данных
echo "🗄️ Применяем миграции базы данных..."
alembic upgrade head

# Создаем службу systemd
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
EnvironmentFile=/home/wb_bot_user/bot_postavki/config_ionos.env
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

# Создаем пользователя для бота
echo "👤 Создаем пользователя для бота..."
sudo useradd --create-home --shell /bin/bash wb_bot_user
sudo chown -R wb_bot_user:wb_bot_user /home/wb_bot_user

# Копируем файлы проекта
echo "📁 Копируем файлы проекта..."
sudo cp -r . /home/wb_bot_user/bot_postavki/
sudo chown -R wb_bot_user:wb_bot_user /home/wb_bot_user/bot_postavki

# Запускаем службу
echo "🚀 Запускаем службу бота..."
sudo systemctl daemon-reload
sudo systemctl enable wb-bot.service
sudo systemctl start wb-bot.service

# Настраиваем nginx (опционально для webhook)
echo "🌐 Настраиваем nginx для webhook..."
sudo tee /etc/nginx/sites-available/wb-bot > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/wb-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

echo "✅ Развертывание завершено!"
echo "📋 Следующие шаги:"
echo "1. Настройте DNS для вашего домена на Ionos"
echo "2. Получите SSL сертификат: sudo certbot --nginx -d your-domain.com"
echo "3. Обновите config_ionos.env с реальными значениями"
echo "4. Перезапустите бота: sudo systemctl restart wb-bot.service"
echo "5. Проверьте статус: sudo systemctl status wb-bot.service"
echo "6. Посмотрите логи: sudo journalctl -u wb-bot.service -f"
