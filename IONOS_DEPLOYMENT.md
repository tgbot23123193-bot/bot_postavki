# 🚀 Развертывание WB Bot на Ionos Ubuntu

## 📋 Предварительные требования

- Ubuntu сервер на Ionos
- Доменное имя (опционально, но рекомендуется)
- SSH доступ к серверу

## 🛠️ Шаг 1: Подготовка сервера

### 1.1 Подключение к серверу

```bash
ssh root@your-server-ip
```

### 1.2 Обновление системы

```bash
apt update && apt upgrade -y
```

### 1.3 Установка необходимых пакетов

```bash
apt install -y curl wget git htop nano ufw
```

### 1.4 Настройка firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

## 🗄️ Шаг 2: Установка и настройка базы данных

### 2.1 Установка PostgreSQL

```bash
apt install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql
```

### 2.2 Создание базы данных и пользователя

```bash
sudo -u postgres psql

# В psql выполнить:
CREATE USER wb_bot_user WITH PASSWORD 'your_secure_password_here';
CREATE DATABASE wb_bot_prod OWNER wb_bot_user;
GRANT ALL PRIVILEGES ON DATABASE wb_bot_prod TO wb_bot_user;
\q
```

### 2.3 Установка Redis

```bash
apt install -y redis-server
systemctl start redis-server
systemctl enable redis-server
```

## 🐍 Шаг 3: Установка Python и зависимостей

### 3.1 Установка Python 3.11

```bash
apt install -y python3.11 python3.11-pip python3.11-venv
```

### 3.2 Установка Node.js (для Playwright)

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
```

## 📦 Шаг 4: Развертывание приложения

### 4.1 Клонирование репозитория

```bash
cd /home
git clone https://github.com/your-repo/bot_postavki.git
cd bot_postavki
```

### 4.2 Создание виртуального окружения

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 4.3 Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.4 Установка Playwright браузеров

```bash
playwright install chromium
playwright install-deps
```

### 4.5 Настройка конфигурации

```bash
cp config_ionos.env .env
nano .env
```

**Важно:** Заполните все плейсхолдеры в `.env` реальными значениями:
- `TG_BOT_TOKEN` - токен от BotFather
- `DATABASE_URL` - строка подключения к PostgreSQL
- `SECURITY_ENCRYPTION_KEY` и `SECURITY_JWT_SECRET` - сгенерируйте новые
- `TG_WEBHOOK_URL` - URL вашего домена для webhook

### 4.6 Применение миграций базы данных

```bash
alembic upgrade head
```

## ⚙️ Шаг 5: Настройка systemd службы

### 5.1 Создание пользователя для бота

```bash
useradd --create-home --shell /bin/bash wb_bot_user
```

### 5.2 Создание службы

```bash
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

[Install]
WantedBy=multi-user.target
EOF
```

### 5.3 Копирование файлов проекта

```bash
cp -r /home/bot_postavki /home/wb_bot_user/
chown -R wb_bot_user:wb_bot_user /home/wb_bot_user/bot_postavki
```

### 5.4 Запуск службы

```bash
systemctl daemon-reload
systemctl enable wb-bot.service
systemctl start wb-bot.service
```

## 🌐 Шаг 6: Настройка Nginx (опционально)

### 6.1 Установка Nginx

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 6.2 Настройка сайта

```bash
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

ln -s /etc/nginx/sites-available/wb-bot /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 6.3 Получение SSL сертификата

```bash
certbot --nginx -d your-domain.com
```

## 🔍 Шаг 7: Проверка развертывания

### 7.1 Проверка статуса служб

```bash
systemctl status postgresql redis-server wb-bot nginx
```

### 7.2 Проверка логов

```bash
journalctl -u wb-bot.service -f
```

### 7.3 Тестирование health endpoint

```bash
curl http://localhost:8000/health
```

### 7.4 Проверка подключения к базе данных

```bash
sudo -u postgres psql -d wb_bot_prod -c "SELECT COUNT(*) FROM users;"
```

## 🛠️ Управление ботом

### Перезапуск бота
```bash
sudo systemctl restart wb-bot.service
```

### Просмотр логов
```bash
sudo journalctl -u wb-bot.service -f
```

### Статус бота
```bash
sudo systemctl status wb-bot.service
```

### Остановка бота
```bash
sudo systemctl stop wb-bot.service
```

## 🔧 Обновление бота

```bash
cd /home/wb_bot_user/bot_postavki
sudo -u wb_bot_user git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart wb-bot.service
```

## 📊 Мониторинг

### Системные ресурсы
```bash
htop
```

### Дисковое пространство
```bash
df -h
```

### Активные соединения
```bash
netstat -tlnp
```

## 🔒 Безопасность

1. **Измените пароли по умолчанию** в PostgreSQL и других сервисах
2. **Настройте SSH ключи** вместо паролей
3. **Регулярно обновляйте систему**: `apt update && apt upgrade`
4. **Настройте мониторинг** и уведомления о проблемах
5. **Создайте резервные копии** базы данных регулярно

## 🆘 Поиск и устранение неисправностей

### Проблемы с ботом
- Проверьте логи: `journalctl -u wb-bot.service -f`
- Убедитесь что все переменные окружения заполнены
- Проверьте подключение к базе данных

### Проблемы с базой данных
- Проверьте статус: `systemctl status postgresql`
- Проверьте логи: `journalctl -u postgresql.service -f`
- Тестируйте подключение: `psql -h localhost -d wb_bot_prod -U wb_bot_user`

### Проблемы с вебхуком
- Проверьте настройки Nginx
- Убедитесь что порт 8000 открыт
- Проверьте firewall: `ufw status`

## 📞 Поддержка

Если у вас возникли проблемы:
1. Проверьте логи всех служб
2. Убедитесь что все конфигурационные файлы заполнены
3. Проверьте подключение к внешним сервисам (Telegram, Wildberries API)
4. Обратитесь к документации Ionos для специфичных настроек сервера
