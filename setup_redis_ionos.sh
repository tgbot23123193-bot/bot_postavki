#!/bin/bash

# Redis Setup Script for Ionos Ubuntu

echo "🔄 Настройка Redis для WB Bot на Ionos..."

# Устанавливаем Redis если не установлен
if ! dpkg -l | grep -q redis-server; then
    echo "📦 Устанавливаем Redis..."
    sudo apt update
    sudo apt install -y redis-server
fi

# Настраиваем Redis для продакшена
echo "⚙️ Настраиваем Redis конфигурацию..."

sudo tee /etc/redis/redis.conf > /dev/null <<EOF
# Основные настройки
bind 127.0.0.1 ::1
port 6379
timeout 0
tcp-keepalive 300
daemonize yes
supervised systemd
loglevel notice
logfile /var/log/redis/redis-server.log

# Память
maxmemory 256mb
maxmemory-policy allkeys-lru

# Сохранение данных
save 900 1
save 300 10
save 60 10000

# Безопасность
requirepass your_secure_redis_password_here

# AOF (Append Only File)
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec

# RDB (Redis Database Backup)
dbfilename dump.rdb
dir /var/lib/redis

# Максимальное количество клиентов
maxclients 10000
EOF

# Создаем пользователя для Redis
sudo usermod -aG redis wb_bot_user

# Создаем директорию для логов
sudo mkdir -p /var/log/redis
sudo chown redis:redis /var/log/redis
sudo chmod 755 /var/log/redis

# Перезапускаем Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server

# Тестируем Redis
echo "🔍 Тестируем Redis..."
redis-cli ping

echo "✅ Redis настроен!"
echo ""
echo "📋 Информация для подключения:"
echo "Хост: localhost"
echo "Порт: 6379"
echo "Пароль: your_secure_redis_password_here"
echo ""
echo "💾 REDIS_URL для .env файла:"
echo "redis://:your_secure_redis_password_here@localhost:6379/0"
