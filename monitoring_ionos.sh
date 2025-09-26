#!/bin/bash

# Monitoring Script for Ionos Ubuntu

echo "🔍 Мониторинг WB Bot на Ionos"
echo "=============================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки статуса сервиса
check_service() {
    local service=$1
    if systemctl is-active --quiet $service; then
        echo -e "${GREEN}✅ $service работает${NC}"
    else
        echo -e "${RED}❌ $service остановлен${NC}"
        return 1
    fi
}

echo "📊 Системные сервисы:"
check_service postgresql
check_service redis-server
check_service wb-bot

echo ""
echo "📊 Ресурсы системы:"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')% загрузка"
echo "Память: $(free -h | grep "^Mem:" | awk '{print $3 "/" $2}')"
echo "Диск: $(df -h / | tail -1 | awk '{print $5}') использования"

echo ""
echo "📊 Активные соединения:"
netstat -tlnp 2>/dev/null | grep -E "(LISTEN|5432|6379)" | head -5

echo ""
echo "📊 Логи бота (последние 5 строк):"
if [ -f "/var/log/wb-bot/wb-bot.log" ]; then
    tail -5 /var/log/wb-bot/wb-bot.log
else
    echo "Логи не найдены. Используйте: sudo journalctl -u wb-bot.service -n 10"
fi

echo ""
echo "📊 Статистика базы данных:"
sudo -u postgres psql -d wb_bot_prod -c "
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY tablename, attname;" 2>/dev/null | head -10

echo ""
echo "📋 Рекомендации по мониторингу:"
echo "1. Установите Zabbix или Prometheus для полного мониторинга"
echo "2. Настройте алерты для критических событий"
echo "3. Мониторьте логи на наличие ошибок"
echo "4. Проверяйте производительность базы данных"
echo "5. Следите за использованием дискового пространства"

echo ""
echo "🔧 Команды управления:"
echo "Перезапуск бота: sudo systemctl restart wb-bot.service"
echo "Просмотр логов: sudo journalctl -u wb-bot.service -f"
echo "Статус всех служб: sudo systemctl status postgresql redis-server wb-bot"
echo "Проверка ресурсов: htop"
