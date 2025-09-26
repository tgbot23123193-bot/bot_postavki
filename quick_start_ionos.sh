#!/bin/bash

# Quick Start Script for Ionos Ubuntu

echo "🚀 Быстрый запуск WB Bot на Ionos"
echo "=================================="

# Проверяем что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Пожалуйста запустите скрипт от root: sudo $0"
    exit 1
fi

echo "🔍 Проверяем системные требования..."
REQUIRED_PACKAGES="postgresql redis-server python3.11 nodejs"
for pkg in $REQUIRED_PACKAGES; do
    if dpkg -l | grep -q "^ii  $pkg"; then
        echo "✅ $pkg установлен"
    else
        echo "❌ $pkg не установлен"
        echo "Установите недостающие пакеты: sudo apt install $REQUIRED_PACKAGES"
        exit 1
    fi
done

echo ""
echo "🗄️ Настраиваем базу данных..."
systemctl start postgresql
systemctl enable postgresql

# Создаем базу данных если она не существует
if ! sudo -u postgres psql -l | grep -q wb_bot_prod; then
    DB_PASSWORD=$(openssl rand -base64 32)
    sudo -u postgres psql -c "CREATE USER wb_bot_user WITH PASSWORD '$DB_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE wb_bot_prod OWNER wb_bot_user;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wb_bot_prod TO wb_bot_user;"
    echo "💾 Пароль БД: $DB_PASSWORD"
else
    echo "✅ База данных уже существует"
fi

echo ""
echo "🔄 Настраиваем Redis..."
systemctl start redis-server
systemctl enable redis-server

echo ""
echo "🐍 Настраиваем Python окружение..."
if [ ! -d "/home/wb_bot_user/bot_postavki" ]; then
    useradd --create-home --shell /bin/bash wb_bot_user
    cp -r /root/bot_postavki /home/wb_bot_user/
    chown -R wb_bot_user:wb_bot_user /home/wb_bot_user/bot_postavki
fi

cd /home/wb_bot_user/bot_postavki

# Создаем виртуальное окружение
sudo -u wb_bot_user python3.11 -m venv venv

# Устанавливаем зависимости
sudo -u wb_bot_user bash -c "source venv/bin/activate && pip install --upgrade pip"
sudo -u wb_bot_user bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Устанавливаем Playwright
sudo -u wb_bot_user bash -c "source venv/bin/activate && playwright install chromium"

echo ""
echo "⚙️ Применяем миграции..."
sudo -u wb_bot_user bash -c "source venv/bin/activate && alembic upgrade head"

echo ""
echo "🚀 Запускаем бота..."
systemctl daemon-reload
systemctl enable wb-bot.service
systemctl start wb-bot.service

echo ""
echo "✅ Быстрый запуск завершен!"
echo ""
echo "📊 Проверьте статус:"
echo "sudo systemctl status wb-bot.service"
echo ""
echo "📋 Просмотр логов:"
echo "sudo journalctl -u wb-bot.service -f"
echo ""
echo "🔧 Если есть проблемы:"
echo "1. Проверьте что все переменные в .env заполнены"
echo "2. Убедитесь что токен бота корректный"
echo "3. Проверьте подключение к Wildberries API"
echo ""
echo "🎉 Ваш бот должен быть доступен в Telegram!"
