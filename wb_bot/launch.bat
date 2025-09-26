@echo off
REM Запуск браузера пользователя (Windows)
echo 🚀 Запуск браузера для пользователя %1
echo.

if "%1"=="" (
    echo ❌ Ошибка: Не указан ID пользователя
    echo 💡 Использование: launch.bat USER_ID
    echo 💡 Пример: launch.bat 123456789
    pause
    exit /b 1
)

python launch_browser.py %1

pause


