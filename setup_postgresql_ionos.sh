#!/bin/bash

# PostgreSQL Setup Script for Ionos Ubuntu

echo "🗄️ Настройка PostgreSQL для WB Bot на Ionos..."

# Устанавливаем PostgreSQL если не установлен
if ! dpkg -l | grep -q postgresql; then
    echo "📦 Устанавливаем PostgreSQL..."
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi

# Создаем пользователя и базу данных
echo "👤 Создаем пользователя и базу данных..."

# Генерируем безопасный пароль
DB_PASSWORD=$(openssl rand -base64 32)
echo "🔐 Сгенерированный пароль для БД: $DB_PASSWORD"

sudo -u postgres psql -c "CREATE USER wb_bot_user WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE wb_bot_prod OWNER wb_bot_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wb_bot_prod TO wb_bot_user;"

# Настраиваем PostgreSQL для продакшена
echo "⚙️ Настраиваем PostgreSQL конфигурацию..."

sudo tee /etc/postgresql/*/main/postgresql.conf > /dev/null <<EOF
# Основные настройки
listen_addresses = '*'
port = 5432
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.7
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 2GB

# Логирование
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_statement = 'ddl'
log_min_duration_statement = 1000
log_duration = on
log_lock_waits = on
EOF

# Настраиваем pg_hba.conf для безопасного доступа
echo "🔒 Настраиваем доступ к базе данных..."
sudo tee /etc/postgresql/*/main/pg_hba.conf > /dev/null <<EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     peer
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    wb_bot_prod     wb_bot_user     0.0.0.0/0               md5
EOF

# Перезапускаем PostgreSQL
sudo systemctl restart postgresql

echo "✅ PostgreSQL настроен!"
echo ""
echo "📋 Информация для подключения:"
echo "Хост: localhost"
echo "Порт: 5432"
echo "База данных: wb_bot_prod"
echo "Пользователь: wb_bot_user"
echo "Пароль: $DB_PASSWORD"
echo ""
echo "💾 DATABASE_URL для .env файла:"
echo "postgresql://wb_bot_user:$DB_PASSWORD@localhost:5432/wb_bot_prod"
echo ""
echo "⚠️  Сохраните пароль в безопасном месте!"
