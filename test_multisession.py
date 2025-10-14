#!/usr/bin/env python3
"""
Тест мультисессии браузеров.
Проверяет что разные пользователи получают разные браузеры.
"""

import asyncio
from wb_bot.app.services.browser_manager import browser_manager
from wb_bot.app.utils.logger import get_logger

logger = get_logger(__name__)


async def test_multisession():
    """Тестирование мультисессии."""
    logger.info("🧪 Начинаю тест мультисессии...")
    
    # Тестируем двух пользователей
    user1_id = 123456789
    user2_id = 987654321
    
    try:
        # Создаем браузер для первого пользователя
        logger.info(f"\n{'='*60}")
        logger.info(f"📝 Создаю браузер для пользователя {user1_id}")
        logger.info(f"{'='*60}")
        browser1 = await browser_manager.get_browser(
            user_id=user1_id, 
            headless=True, 
            debug_mode=True
        )
        
        if browser1:
            logger.info(f"✅ Браузер 1 создан:")
            logger.info(f"   - Порт: {browser1.debug_port}")
            logger.info(f"   - Папка данных: {browser1.user_data_dir}")
            logger.info(f"   - Файл cookies: {browser1.cookies_file}")
        else:
            logger.error(f"❌ Не удалось создать браузер для пользователя {user1_id}")
            return False
        
        # Создаем браузер для второго пользователя
        logger.info(f"\n{'='*60}")
        logger.info(f"📝 Создаю браузер для пользователя {user2_id}")
        logger.info(f"{'='*60}")
        browser2 = await browser_manager.get_browser(
            user_id=user2_id, 
            headless=True, 
            debug_mode=True
        )
        
        if browser2:
            logger.info(f"✅ Браузер 2 создан:")
            logger.info(f"   - Порт: {browser2.debug_port}")
            logger.info(f"   - Папка данных: {browser2.user_data_dir}")
            logger.info(f"   - Файл cookies: {browser2.cookies_file}")
        else:
            logger.error(f"❌ Не удалось создать браузер для пользователя {user2_id}")
            return False
        
        # Проверяем что браузеры разные
        logger.info(f"\n{'='*60}")
        logger.info("🔍 Проверка изоляции браузеров")
        logger.info(f"{'='*60}")
        
        checks_passed = True
        
        # Проверка 1: Разные порты
        if browser1.debug_port != browser2.debug_port:
            logger.info(f"✅ Порты разные: {browser1.debug_port} ≠ {browser2.debug_port}")
        else:
            logger.error(f"❌ ОШИБКА: Порты одинаковые: {browser1.debug_port} = {browser2.debug_port}")
            checks_passed = False
        
        # Проверка 2: Разные папки данных
        if browser1.user_data_dir != browser2.user_data_dir:
            logger.info(f"✅ Папки данных разные:")
            logger.info(f"   - Браузер 1: {browser1.user_data_dir}")
            logger.info(f"   - Браузер 2: {browser2.user_data_dir}")
        else:
            logger.error(f"❌ ОШИБКА: Папки данных одинаковые")
            checks_passed = False
        
        # Проверка 3: Разные файлы cookies
        if browser1.cookies_file != browser2.cookies_file:
            logger.info(f"✅ Файлы cookies разные:")
            logger.info(f"   - Браузер 1: {browser1.cookies_file}")
            logger.info(f"   - Браузер 2: {browser2.cookies_file}")
        else:
            logger.error(f"❌ ОШИБКА: Файлы cookies одинаковые")
            checks_passed = False
        
        # Проверка 4: Разные экземпляры браузеров
        if browser1 is not browser2:
            logger.info(f"✅ Экземпляры браузеров разные (id: {id(browser1)} ≠ {id(browser2)})")
        else:
            logger.error(f"❌ ОШИБКА: Экземпляры браузеров одинаковые")
            checks_passed = False
        
        # Проверка 5: Активные пользователи
        active_users = browser_manager.get_active_users()
        logger.info(f"\n📊 Активные пользователи: {active_users}")
        if user1_id in active_users and user2_id in active_users:
            logger.info(f"✅ Оба пользователя активны")
        else:
            logger.error(f"❌ ОШИБКА: Не все пользователи активны")
            checks_passed = False
        
        # Проверка 6: Повторное получение браузера
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 Проверка повторного получения браузера")
        logger.info(f"{'='*60}")
        browser1_again = await browser_manager.get_browser(user_id=user1_id)
        if browser1_again is browser1:
            logger.info(f"✅ Повторное получение возвращает тот же браузер (переиспользование)")
        else:
            logger.error(f"❌ ОШИБКА: Повторное получение создало новый браузер")
            checks_passed = False
        
        # Закрываем браузеры
        logger.info(f"\n{'='*60}")
        logger.info("🔒 Закрываю браузеры")
        logger.info(f"{'='*60}")
        await browser_manager.close_browser(user1_id)
        logger.info(f"✅ Браузер пользователя {user1_id} закрыт")
        
        await browser_manager.close_browser(user2_id)
        logger.info(f"✅ Браузер пользователя {user2_id} закрыт")
        
        # Итоговый результат
        logger.info(f"\n{'='*60}")
        if checks_passed:
            logger.info("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Мультисессия работает корректно!")
        else:
            logger.error("❌ НЕКОТОРЫЕ ПРОВЕРКИ ПРОВАЛЕНЫ! Есть проблемы с мультисессией!")
        logger.info(f"{'='*60}\n")
        
        return checks_passed
        
    except Exception as e:
        logger.error(f"❌ Ошибка во время теста: {e}")
        import traceback
        logger.error(f"Трассировка:\n{traceback.format_exc()}")
        return False


async def main():
    """Главная функция."""
    success = await test_multisession()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())


