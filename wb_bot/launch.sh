#!/bin/bash
# Запуск браузера пользователя (Linux/Mac)

if [ $# -eq 0 ]; then
    echo "❌ Ошибка: Не указан ID пользователя"
    echo "💡 Использование: ./launch.sh USER_ID"
    echo "💡 Пример: ./launch.sh 123456789"
    exit 1
fi

USER_ID=$1
echo "🚀 Запуск браузера для пользователя $USER_ID"
echo

python3 launch_browser.py $USER_ID


