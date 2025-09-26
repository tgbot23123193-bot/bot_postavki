#!/bin/bash

# Ionos Deployment Status Check Script

echo "🔍 Проверяем статус развертывания WB Bot на Ionos..."
echo "==============================================="

# Проверяем системные сервисы
echo "📊 Системные сервисы:"
systemctl is-active postgresql && echo "✅ PostgreSQL работает" || echo "❌ PostgreSQL остановлен"
systemctl is-active redis-server && echo "✅ Redis работает" || echo "❌ Redis остановлен"
systemctl is-active nginx && echo "✅ Nginx работает" || echo "❌ Nginx остановлен"

echo ""
echo "📊 Служба бота:"
systemctl is-active wb-bot && echo "✅ WB Bot работает" || echo "❌ WB Bot остановлен"

echo ""
echo "📊 Использование ресурсов:"
echo "CPU и память:"
top -bn1 | grep -E "(Cpu|Mem|Tasks)" | head -3

echo ""
echo "📊 Дисковое пространство:"
df -h

echo ""
echo "📊 Активные соединения:"
netstat -tlnp | grep -E "(LISTEN|5432|6379|8000)"

echo ""
echo "📊 Логи бота (последние 10 строк):"
if [ -f "/var/log/wb-bot/wb-bot.log" ]; then
    tail -10 /var/log/wb-bot/wb-bot.log
else
    echo "Логов не найдено. Проверьте: sudo journalctl -u wb-bot.service -f"
fi

echo ""
echo "📊 Статус базы данных:"
sudo -u postgres psql -d wb_bot_prod -c "SELECT COUNT(*) as users_count FROM users;" 2>/dev/null || echo "❌ Не удалось подключиться к БД"

echo ""
echo "📋 Рекомендации:"
echo "1. Проверьте логи: sudo journalctl -u wb-bot.service -f"
echo "2. Статус сервисов: sudo systemctl status postgresql redis-server nginx wb-bot"
echo "3. Перезапуск: sudo systemctl restart wb-bot.service"
echo "4. Просмотр логов в реальном времени: sudo journalctl -u wb-bot.service -f"
