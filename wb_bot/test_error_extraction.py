#!/usr/bin/env python3
"""
Тестовый скрипт для проверки извлечения ошибок из WB.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.services.browser_manager import BrowserManager
from app.services.redistribution_service import get_redistribution_service
from app.database.connection import init_database, close_database
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def test_error_extraction(user_id: int):
    """Тестируем извлечение ошибок из WB."""
    await init_database()
    
    try:
        browser_manager = BrowserManager()
        redistribution_service = get_redistribution_service(browser_manager, fast_mode=False)
        
        # Запускаем браузер
        logger.info(f"🚀 Запуск браузера для пользователя {user_id}...")
        browser = await browser_manager.get_browser(user_id, headless=False, debug_mode=True)
        if not browser:
            logger.error("❌ Не удалось запустить браузер")
            return
        
        page = browser.page
        if not page:
            logger.error("❌ Не удалось получить страницу")
            return
        
        # Открываем страницу перераспределения
        logger.info("📄 Открытие страницы перераспределения...")
        result = await redistribution_service.open_redistribution_page(user_id)
        if not result["success"]:
            logger.error(f"❌ Ошибка открытия страницы: {result['error']}")
            return
        
        logger.info("✅ Страница открыта успешно")
        
        # Теперь ищем все возможные ошибки на странице
        logger.info("🔍 Поиск ошибок на странице...")
        
        # Селекторы ошибок
        error_selectors = [
            "span.Form-select-input__error_0o5Vr-u",
            "span[class*='Form-select-input__error_0o5Vr-u']",
            "span[class*='Form-select-input__error']",
            "span.Form-select-input__error_Qp5MtLu", 
            "[class*='Form-select-input__error']",
            "[class*='error'][class*='form']",
            "[class*='error'][class*='select']",
            ".error-message",
            "[data-testid*='error']"
        ]
        
        found_errors = []
        
        for selector in error_selectors:
            try:
                error_elements = await page.query_selector_all(selector)
                logger.info(f"🔍 Селектор '{selector}': найдено {len(error_elements)} элементов")
                
                for i, element in enumerate(error_elements):
                    try:
                        is_visible = await element.is_visible()
                        text = await element.text_content()
                        class_name = await element.get_attribute("class")
                        
                        logger.info(f"  📝 Элемент {i}: visible={is_visible}, text='{text}', class='{class_name}'")
                        
                        if is_visible and text and text.strip():
                            cleaned_text = text.strip()
                            if cleaned_text not in found_errors:
                                found_errors.append(cleaned_text)
                                logger.warning(f"⚠️ НАЙДЕНА ОШИБКА: {cleaned_text}")
                    except Exception as e:
                        logger.debug(f"Ошибка при обработке элемента: {e}")
                        
            except Exception as e:
                logger.debug(f"Ошибка поиска по селектору {selector}: {e}")
        
        # XPath поиск
        xpath_selectors = [
            "//*[contains(text(), 'лимит')]",
            "//*[contains(text(), 'Дневной')]", 
            "//*[contains(text(), 'исчерпан')]",
            "//*[contains(text(), 'Переместите')]",
            "//*[contains(text(), 'ошибка')]"
        ]
        
        for xpath in xpath_selectors:
            try:
                elements = await page.locator(f"xpath={xpath}").all()
                logger.info(f"🔍 XPath '{xpath}': найдено {len(elements)} элементов")
                
                for i, element in enumerate(elements):
                    try:
                        is_visible = await element.is_visible()
                        text = await element.text_content()
                        
                        logger.info(f"  📝 XPath элемент {i}: visible={is_visible}, text='{text}'")
                        
                        if is_visible and text and text.strip():
                            cleaned_text = text.strip()
                            if cleaned_text not in found_errors and len(cleaned_text) > 10:
                                found_errors.append(cleaned_text)
                                logger.warning(f"⚠️ НАЙДЕНА ОШИБКА XPATH: {cleaned_text}")
                    except Exception as e:
                        logger.debug(f"Ошибка при обработке XPath элемента: {e}")
                        
            except Exception as e:
                logger.debug(f"Ошибка XPath поиска {xpath}: {e}")
        
        # Расширенный поиск
        logger.info("🔍 Расширенный поиск по ключевым словам...")
        broader_search_terms = [
            "дневной лимит",
            "лимит исчерпан", 
            "переместите товар",
            "попробуйте завтра",
            "недоступен",
            "ошибка"
        ]
        
        for term in broader_search_terms:
            try:
                xpath_selector = f"//*[contains(translate(text(), 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'), '{term.lower()}')]"
                elements = await page.locator(f"xpath={xpath_selector}").all()
                logger.info(f"🔍 Расширенный поиск '{term}': найдено {len(elements)} элементов")
                
                for i, element in enumerate(elements):
                    try:
                        is_visible = await element.is_visible()
                        text = await element.text_content()
                        
                        logger.info(f"  📝 Расширенный элемент {i}: visible={is_visible}, text='{text}'")
                        
                        if is_visible and text and text.strip() and len(text.strip()) > 10:
                            cleaned_text = text.strip()
                            if cleaned_text not in found_errors:
                                found_errors.append(cleaned_text)
                                logger.warning(f"⚠️ НАЙДЕНА ОШИБКА РАСШИРЕННЫМ ПОИСКОМ: {cleaned_text}")
                                break  # Берем первое релевантное сообщение
                    except Exception as e:
                        logger.debug(f"Ошибка при обработке расширенного элемента: {e}")
                        
            except Exception as e:
                logger.debug(f"Ошибка расширенного поиска по термину '{term}': {e}")
        
        # Итоги
        if found_errors:
            logger.info(f"🎯 НАЙДЕНО ОШИБОК: {len(found_errors)}")
            for i, error in enumerate(found_errors, 1):
                logger.info(f"  {i}. {error}")
        else:
            logger.info("ℹ️ Ошибки не найдены на странице")
        
        # Делаем скриншот
        screenshot_path = f"screenshots_{user_id}/error_extraction_test.png"
        Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
        await page.screenshot(path=screenshot_path)
        logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
        
        # Оставляем браузер открытым для изучения
        logger.info("🖥️ Браузер оставлен открытым для анализа. Нажмите Ctrl+C для завершения.")
        while True:
            await asyncio.sleep(60)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Тест прерван пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}")
    finally:
        await close_database()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Укажите USER_ID")
        logger.info("💡 Пример: python test_error_extraction.py 123456789")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        asyncio.run(test_error_extraction(user_id))
    except ValueError:
        logger.error("❌ USER_ID должен быть числом")
        sys.exit(1)


