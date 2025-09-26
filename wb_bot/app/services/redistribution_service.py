"""
Сервис для перераспределения остатков товаров на Wildberries.

Обеспечивает автоматизацию работы со страницей
https://seller.wildberries.ru/analytics-reports/warehouse-remains
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

from playwright.async_api import Page, Browser, BrowserContext
from ..utils.logger import get_logger
from ..services.browser_manager import BrowserManager
from ..services.database_service import db_service
from ..database.models import User, BrowserSession

logger = get_logger(__name__)


class WBRedistributionService:
    """Сервис для автоматизации перераспределения остатков на Wildberries."""
    
    def __init__(self, browser_manager: BrowserManager, fast_mode: bool = True):
        """
        Инициализация сервиса.
        
        Args:
            browser_manager: Менеджер браузерных сессий
            fast_mode: Режим ускоренной работы (убирает лишние скриншоты и логи)
        """
        self.browser_manager = browser_manager
        self.fast_mode = fast_mode
        self.redistribution_url = "https://seller.wildberries.ru/analytics-reports/warehouse-remains"
    
    async def find_warehouses_by_pattern(self, page: Page, pattern_selector: str) -> List[Dict[str, Any]]:
        """
        Ищет склады на основе образца одного элемента.
        
        Args:
            page: Страница браузера
            pattern_selector: Селектор образца склада
            
        Returns:
            Список найденных складов
        """
        warehouses = []
        
        try:
            # Ищем все элементы по образцу
            elements = await page.query_selector_all(pattern_selector)
            logger.info(f"🔍 По образцу '{pattern_selector}' найдено {len(elements)} элементов")
            
            for i, element in enumerate(elements):
                try:
                    text_content = await element.text_content()
                    data_testid = await element.get_attribute("data-testid")
                    class_name = await element.get_attribute("class")
                    tag_name = await element.evaluate("el => el.tagName")
                    
                    if text_content and text_content.strip():
                        warehouse_info = {
                            "id": f"warehouse_{i}",
                            "name": text_content.strip(),
                            "data_testid": data_testid,
                            "class": class_name,
                            "tag": tag_name,
                            "selector": pattern_selector,
                            "element_index": i
                        }
                        warehouses.append(warehouse_info)
                        logger.info(f"📦 Найден склад: '{text_content.strip()}' (testid: {data_testid})")
                except Exception as e:
                    logger.debug(f"Ошибка при обработке элемента {i}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Ошибка поиска по образцу '{pattern_selector}': {e}")
            
        return warehouses
    
    async def open_redistribution_page(self, user_id: int) -> Dict[str, Any]:
        """
        Открывает страницу перераспределения остатков для конкретного пользователя.
        
        Args:
            user_id: ID пользователя из базы данных
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"🔄 Открытие страницы перераспределения для пользователя {user_id}")
            
            # Получаем браузерную сессию из таблицы browser_sessions
            browser_session = await db_service.get_browser_session(user_id)
            if not browser_session:
                return {
                    "success": False,
                    "error": "Браузерная сессия пользователя не найдена в таблице browser_sessions",
                    "user_id": user_id
                }
            
            if not browser_session.session_valid:
                return {
                    "success": False,
                    "error": "Сессия пользователя недействительна в browser_sessions",
                    "user_id": user_id
                }
            
            if not browser_session.wb_login_success:
                return {
                    "success": False,
                    "error": "Пользователь не авторизован в Wildberries. Сначала пройдите авторизацию через бота.",
                    "user_id": user_id,
                    "login_attempts": browser_session.login_attempts,
                    "last_login": browser_session.last_successful_login
                }
            
            logger.info(f"✅ Найдена валидная сессия для пользователя {user_id}")
            logger.info(f"📁 User data dir: {browser_session.user_data_dir}")
            logger.info(f"🍪 Cookies file: {browser_session.cookies_file}")
            logger.info(f"🔑 WB Login success: {browser_session.wb_login_success}")
            logger.info(f"📞 Phone: {browser_session.phone_number}")
            logger.info(f"🕐 Last login: {browser_session.last_successful_login}")
            
            # Получаем браузер с реальной сессией пользователя
            logger.info(f"🚀 Запрос браузера для пользователя {user_id}")
            browser = await self.browser_manager.get_browser(
                user_id=user_id,
                headless=False,  # Показываем браузер для отладки
                debug_mode=True
            )
            
            logger.info(f"📊 Результат получения браузера: {browser}")
            
            if not browser:
                logger.error(f"❌ Браузер не получен для пользователя {user_id}")
                return {
                    "success": False,
                    "error": "Не удалось инициализировать браузер",
                    "user_id": user_id
                }
            
            # Получаем активную страницу
            logger.info(f"🔍 Проверка браузера: {browser}")
            logger.info(f"🔍 Тип браузера: {type(browser)}")
            
            page = browser.page
            logger.info(f"🔍 Страница браузера: {page}")
            
            if not page:
                logger.error(f"❌ Страница браузера None! Браузер: {browser}")
                return {
                    "success": False,
                    "error": "Не удалось получить активную страницу браузера",
                    "user_id": user_id,
                    "debug_info": {
                        "browser_exists": browser is not None,
                        "browser_type": str(type(browser)),
                        "page_exists": page is not None
                    }
                }
            
            logger.info(f"🌐 Переход на страницу: {self.redistribution_url}")
            
            # Переходим на страницу перераспределения
            response = await page.goto(self.redistribution_url, wait_until="networkidle")
            
            if not response or response.status != 200:
                return {
                    "success": False,
                    "error": f"Ошибка загрузки страницы: статус {response.status if response else 'None'}",
                    "user_id": user_id,
                    "url": self.redistribution_url
                }
            
            logger.info(f"✅ Страница загружена успешно")
            
            # Ждем полной загрузки страницы
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.3)  # Дополнительная пауза для загрузки JS
            
            # Проверяем что мы на правильной странице
            current_url = page.url
            page_title = await page.title()
            
            logger.info(f"📄 Текущий URL: {current_url}")
            logger.info(f"📄 Заголовок страницы: {page_title}")
            
            # Ищем элементы страницы перераспределения
            redistribution_elements = await self._find_redistribution_elements(page, user_id)
            
            # Ищем и кликаем кнопку обновления данных (из скриншота)
            refresh_button_found = False
            refresh_button_selectors = [
                # Точные селекторы из скриншота
                "span.Button-link_icon_recZqdV\\+k.Button-link_icon--left_big_SMVcmQdSt.Button-link_icon--no-text_7w1r\\+5WDRA",
                "span[class*='Button-link_icon_recZqdV'][class*='Button-link_icon--left_big_SMVcmQdSt'][class*='Button-link_icon--no-text_7w1r']",
                
                # Более общие селекторы
                "span[class*='Button-link_icon'][class*='Button-link_icon--left_big'][class*='Button-link_icon--no-text']",
                "span[class*='Button-link_icon_recZqdV']",
                "span[class*='Button-link_icon--left_big_SMVcmQdSt']",
                "span[class*='Button-link_icon--no-text_7w1r']",
                
                # По иконке обновления
                "[data-testid*='refresh']",
                "[class*='refresh']",
                "[title*='обновить']",
                "[title*='Обновить']"
            ]
            
            logger.info("🔄 Поиск кнопки обновления данных...")
            
            for selector in refresh_button_selectors:
                try:
                    refresh_button = await page.query_selector(selector)
                    if refresh_button and await refresh_button.is_visible():
                        logger.info(f"✅ Найдена кнопка обновления: {selector}")
                        await refresh_button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.1)
                        await refresh_button.click()
                        await asyncio.sleep(1.5)  # Ждем 1-2 секунды как просил пользователь
                        refresh_button_found = True
                        logger.info("🔄 Кнопка обновления нажата, ждем обновления данных...")
                        break
                except Exception as e:
                    logger.debug(f"Кнопка обновления не найдена по селектору {selector}: {e}")
                    continue
            
            if not refresh_button_found:
                logger.warning("⚠️ Кнопка обновления не найдена, продолжаем без обновления")
            
            return {
                "success": True,
                "message": "Страница перераспределения открыта успешно",
                "user_id": user_id,
                "url": current_url,
                "refresh_button_clicked": refresh_button_found,
                "page_title": page_title,
                "elements_found": redistribution_elements,
                "session_data": {
                    "wb_login_success": browser_session.wb_login_success,
                    "last_successful_login": browser_session.last_successful_login
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка при открытии страницы перераспределения: {e}")
            return {
                "success": False,
                "error": f"Исключение: {str(e)}",
                "user_id": user_id
            }
    
    async def _find_redistribution_elements(self, page: Page, user_id: int) -> Dict[str, Any]:
        """
        Ищет элементы для перераспределения на странице.
        
        Args:
            page: Страница браузера
            user_id: ID пользователя для скриншотов
            
        Returns:
            Dict с найденными элементами
        """
        try:
            elements = {
                "redistribution_button": None,
                "filters_button": None,
                "table_found": False,
                "data_rows": 0
            }
            
            # Ищем кнопку "Перераспределить остатки"
            redistribution_selectors = [
                'button:has-text("Перераспределить остатки")',
                'button:has-text("Перераспределить")',
                '[data-testid*="redistrib"]',
                '.redistribution-button',
                'button[aria-label*="перераспредел"]'
            ]
            
            for selector in redistribution_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        text = await element.text_content()
                        elements["redistribution_button"] = {
                            "selector": selector,
                            "visible": is_visible,
                            "text": text
                        }
                        logger.info(f"🔍 Найдена кнопка перераспределения: {selector} (видима: {is_visible})")
                        break
                except Exception:
                    continue
            
            # Ищем кнопку фильтров
            filters_selectors = [
                'button:has-text("Фильтры")',
                '[data-testid*="filter"]',
                '.filters-button',
                'button[aria-label*="фильтр"]'
            ]
            
            for selector in filters_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        text = await element.text_content()
                        elements["filters_button"] = {
                            "selector": selector,
                            "visible": is_visible,
                            "text": text
                        }
                        logger.info(f"🔍 Найдена кнопка фильтров: {selector} (видима: {is_visible})")
                        break
                except Exception:
                    continue
            
            # Ищем таблицу с данными остатков
            table_selectors = [
                'table',
                '[role="table"]',
                '.data-table',
                '[data-testid*="table"]'
            ]
            
            for selector in table_selectors:
                try:
                    table = await page.query_selector(selector)
                    if table:
                        rows = await table.query_selector_all('tr, [role="row"]')
                        elements["table_found"] = True
                        elements["data_rows"] = len(rows)
                        logger.info(f"📊 Найдена таблица с {len(rows)} строками")
                        break
                except Exception:
                    continue
            
            # Получаем скриншот страницы для отладки
            screenshot_path = f"screenshots_{user_id}/redistribution_page.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
            
            return elements
            
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске элементов: {e}")
            return {"error": str(e)}
    
    async def click_redistribution_menu(self, user_id: int) -> Dict[str, Any]:
        """
        Кликает по кнопке "Перераспределить остатки" чтобы открыть меню.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"🖱️ Клик по меню перераспределения для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id=user_id)
            if not browser:
                return {
                    "success": False,
                    "error": "Браузер пользователя не найден"
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Активная страница не найдена"
                }
            
            # Ищем и кликаем по кнопке перераспределения
            redistribution_selectors = [
                'button:has-text("Перераспределить остатки")',
                'button:has-text("Перераспределить")',
                '[data-testid*="redistrib"]',
                '.redistribution-button'
            ]
            
            button_clicked = False
            for selector in redistribution_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info(f"✅ Кликнул по кнопке: {selector}")
                        button_clicked = True
                        break
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось кликнуть по {selector}: {e}")
                    continue
            
            if not button_clicked:
                return {
                    "success": False,
                    "error": "Кнопка перераспределения не найдена или не видна"
                }
            
            # Ждем появления меню
            await asyncio.sleep(0.3)
            
            # Делаем скриншот после клика
            screenshot_path = f"screenshots_{user_id}/after_redistribution_click.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"📸 Скриншот после клика: {screenshot_path}")
            
            return {
                "success": True,
                "message": "Кнопка перераспределения нажата успешно",
                "user_id": user_id,
                "screenshot": screenshot_path
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка при клике по меню: {e}")
            return {
                "success": False,
                "error": f"Исключение: {str(e)}",
                "user_id": user_id
            }
    
    async def click_redistribution_menu_and_fill_article(self, user_id: int, article: str) -> Dict[str, Any]:
        """
        Нажимает на кнопку 'Перенести поставку' и заполняет поле артикула.
        
        Args:
            user_id: ID пользователя
            article: Артикул товара для ввода
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"🖱️ Клик по кнопке и заполнение артикула {article} для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # Шаг 1: Ищем и кликаем кнопку "Перенести поставку"
            transfer_selectors = [
                "button:has-text('Перенести поставку')",
                "button:has-text('Перераспределить остатки')",
                "button:has-text('Перераспределить')",
                "button:has-text('Перенести')",
                "[data-testid*='transfer']",
                "[data-testid*='redistribute']",
                ".transfer-button",
                ".redistribute-button"
            ]
            
            button_found = False
            for selector in transfer_selectors:
                try:
                    logger.info(f"🔍 Поиск кнопки 'Перенести поставку' по селектору: {selector}")
                    button = await page.wait_for_selector(selector, timeout=2000)
                    if button:
                        logger.info(f"✅ Найдена кнопка 'Перенести поставку': {selector}")
                        # Прокручиваем к кнопке и кликаем
                        await button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        await button.click()
                        button_found = True
                        logger.info("✅ Кнопка 'Перенести поставку' нажата")
                        break
                except Exception as e:
                    logger.debug(f"Кнопка не найдена по селектору {selector}: {e}")
                    continue
            
            if not button_found:
                logger.warning("⚠️ Кнопка 'Перенести поставку' не найдена")
                # Делаем скриншот для отладки
                screenshot_path = f"screenshots_{user_id}/no_transfer_button.png"
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path, full_page=True)
                return {
                    "success": False,
                    "error": "Кнопка 'Перенести поставку' не найдена на странице",
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
            
            # Ждем появления формы/модального окна
            await asyncio.sleep(0.3)
            
            # Шаг 2: Ищем и кликаем по полю "Введите артикул WB" (первый клик)
            primary_field_selectors = [
                "input[placeholder*='Введите артикул WB']",
                "input[placeholder*='артикул WB']",
                "input[placeholder*='Артикул WB']",
                ".input-field[placeholder*='WB']",
                "[data-testid*='article-wb']"
            ]
            
            primary_field_found = False
            for selector in primary_field_selectors:
                try:
                    logger.info(f"🔍 Поиск основного поля 'Введите артикул WB' по селектору: {selector}")
                    primary_field = await page.wait_for_selector(selector, timeout=2000)
                    if primary_field:
                        logger.info(f"✅ Найдено основное поле 'Введите артикул WB': {selector}")
                        
                        # Кликаем по основному полю
                        await primary_field.click()
                        await asyncio.sleep(0.3)
                        
                        primary_field_found = True
                        logger.info("✅ Кликнули по основному полю 'Введите артикул WB'")
                        break
                except Exception as e:
                    logger.debug(f"Основное поле не найдено по селектору {selector}: {e}")
                    continue
            
            if not primary_field_found:
                logger.warning("⚠️ Основное поле 'Введите артикул WB' не найдено")
                # Пробуем найти любое поле с артикулом
                logger.info("🔄 Попробуем найти любое поле для артикула...")
            
            # Ждем активации поля после клика
            await asyncio.sleep(0.3)
            
            # Шаг 3: Сразу начинаем вводить артикул (поле уже активно после первого клика)
            if primary_field_found:
                logger.info(f"⌨️ Сразу вводим артикул {article} в активное поле...")
                
                # Очищаем поле на всякий случай
                await page.keyboard.press("Control+a")
                await asyncio.sleep(0.05)
                await page.keyboard.press("Delete")
                await asyncio.sleep(0.05)
                
                # Вводим артикул медленно для надежности
                await page.keyboard.type(article, delay=70)
                await asyncio.sleep(0.3)
                
                # Быстрое ожидание выпадающего списка с товарами
                logger.info(f"⏳ Ждем появления выпадающего списка с товарами...")
                await asyncio.sleep(0.8)
                
                # Делаем скриншот списка для отладки
                debug_screenshot = f"screenshots_{user_id}/dropdown_list_debug.png"
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=debug_screenshot)
                logger.info(f"📸 Скриншот выпадающего списка: {debug_screenshot}")
                
                # Ищем товар в выпадающем списке (точный селектор с скрина)
                product_selectors = [
                    # ТОЧНЫЙ селектор с скрина - div.Custom-rim-option_dFaTla4u
                    f"div.Custom-rim-option_dFaTla4u:has-text('{article}')",
                    f"div[class*='Custom-rim-option']:has-text('{article}')",
                    f".Custom-rim-option_dFaTla4u:has-text('{article}')",
                    # Flex Container как на скрине
                    f"div[class*='Custom-rim-option']:has-text('{article}')",
                    f"div[class*='rim-option']:has-text('{article}')",
                    # Общие селекторы для этого типа элементов
                    f"div[class*='Custom']:has-text('{article}')",
                    f"div[style*='background']:has-text('{article}')",
                    f"div[class*='selected']:has-text('{article}')",
                    f"div[class*='highlighted']:has-text('{article}')",
                    f"div[class*='active']:has-text('{article}')",
                    # Более точные селекторы для выпадающих списков WB
                    f"div[role='option']:has-text('{article}')",
                    f"li[role='option']:has-text('{article}')",
                    f"div[data-testid*='option']:has-text('{article}')",
                    # Fallback селекторы
                    f"div:has-text('{article}')",
                    f"li:has-text('{article}')",
                    # Селекторы без текста для поиска по классу
                    "div.Custom-rim-option_dFaTla4u",
                    "div[class*='Custom-rim-option']",
                    "div[class*='rim-option']",
                    "div[role='option']",
                    "li[role='option']"
                ]
                
                product_found = False
                for selector in product_selectors:
                    try:
                        logger.info(f"🔍 Поиск товара в списке по селектору: {selector}")
                        
                        # Ищем все элементы по селектору
                        elements = await page.query_selector_all(selector)
                        logger.info(f"🔍 Найдено {len(elements)} элементов по селектору: {selector}")
                        
                        for element in elements:
                            try:
                                # Получаем текст элемента и информацию о классах
                                text_content = await element.text_content()
                                class_name = await element.get_attribute("class")
                                logger.info(f"📋 Проверяем элемент: текст='{text_content}', класс='{class_name}'")
                                
                                if text_content and article in text_content:
                                    logger.info(f"✅ Найден товар в списке: {text_content} (класс: {class_name})")
                                    
                                    # Проверяем что элемент видим и в области видимости
                                    if await element.is_visible():
                                        # Получаем координаты элемента для точного клика
                                        bounding_box = await element.bounding_box()
                                        if bounding_box:
                                            logger.info(f"📍 Координаты элемента: {bounding_box}")
                                            
                                            # Наводимся на центр товара (как на скрине)
                                            center_x = bounding_box['x'] + bounding_box['width'] / 2
                                            center_y = bounding_box['y'] + bounding_box['height'] / 2
                                            
                                            await page.mouse.move(center_x, center_y)
                                            await asyncio.sleep(0.3)
                                            logger.info(f"🎯 Навели курсор на центр товара: {text_content}")
                                            
                                            # Кликаем точно по центру элемента
                                            await page.mouse.click(center_x, center_y)
                                            await asyncio.sleep(0.05)
                                            
                                            product_found = True
                                            logger.info(f"✅ Выбран товар из списка: {text_content}")
                                            break
                                        else:
                                            # Fallback к обычному клику если координаты не получены
                                            await element.hover()
                                            await asyncio.sleep(0.3)
                                            await element.click()
                                            await asyncio.sleep(0.05)
                                            
                                            product_found = True
                                            logger.info(f"✅ Выбран товар (fallback клик): {text_content}")
                                            break
                                        
                            except Exception as e:
                                logger.debug(f"Ошибка при обработке элемента списка: {e}")
                                continue
                        
                        if product_found:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Товар не найден в списке по селектору {selector}: {e}")
                        continue
                
                # Если товар не найден в списке, пробуем нажать Enter как fallback
                if not product_found:
                    logger.warning(f"⚠️ Товар с артикулом {article} не найден в выпадающем списке")
                    logger.info("🔄 Пробуем нажать Enter как резервный вариант")
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(0.05)
                
                field_found = True
                logger.info(f"✅ Артикул {article} введен и {'товар выбран из списка' if product_found else 'подтвержден Enter'}")
            else:
                # Если основное поле не найдено, пробуем fallback поиск любого поля
                logger.info("🔄 Основное поле не найдено, пробуем найти любое активное поле...")
                
                fallback_selectors = [
                    "input[placeholder*='артикул']",
                    "input[placeholder*='Артикул']", 
                    "input[placeholder*='Поиск']",
                    "input[type='text']:focus",
                    "input[type='search']:focus",
                    "input:focus"
                ]
                
                field_found = False
                for selector in fallback_selectors:
                    try:
                        logger.info(f"🔍 Fallback поиск поля по селектору: {selector}")
                        fallback_field = await page.wait_for_selector(selector, timeout=1500)
                        if fallback_field:
                            logger.info(f"✅ Найдено fallback поле: {selector}")
                            
                            # Кликаем и вводим
                            await fallback_field.click()
                            await asyncio.sleep(0.3)
                            await fallback_field.fill("")
                            await asyncio.sleep(0.05)
                            await fallback_field.type(article, delay=70)
                            await asyncio.sleep(0.3)
                            
                            # Ждем выпадающий список для fallback тоже
                            logger.info("⏳ Ждем появления списка товаров (fallback)...")
                            await asyncio.sleep(0.3)
                            
                            # Пробуем найти товар в списке для fallback
                            fallback_product_found = False
                            elements = await page.query_selector_all(f"div:has-text('{article}'), li:has-text('{article}'), span:has-text('{article}')")
                            
                            for element in elements:
                                try:
                                    text_content = await element.text_content()
                                    if text_content and article in text_content and await element.is_visible():
                                        await element.hover()
                                        await asyncio.sleep(0.05)
                                        await element.click()
                                        fallback_product_found = True
                                        logger.info(f"✅ Fallback: выбран товар из списка {text_content}")
                                        break
                                except:
                                    continue
                            
                            if not fallback_product_found:
                                await fallback_field.press("Enter")
                                logger.info("✅ Fallback: нажат Enter")
                            
                            field_found = True
                            logger.info(f"✅ Fallback: артикул {article} введен и {'товар выбран из списка' if fallback_product_found else 'подтвержден Enter'}")
                            break
                    except Exception as e:
                        logger.debug(f"Fallback поле не найдено по селектору {selector}: {e}")
                        continue
            
            # Делаем финальный скриншот
            screenshot_path = f"screenshots_{user_id}/redistribution_with_article.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path, full_page=True)
            
            if not field_found:
                logger.warning("⚠️ Не удалось ввести артикул ни в одно поле")
                return {
                    "success": False,
                    "error": "Не удалось ввести артикул: поле не активировалось после клика по кнопке",
                    "user_id": user_id,
                    "screenshot": screenshot_path,
                    "button_clicked": button_found,
                    "primary_field_clicked": primary_field_found
                }
            
            return {
                "success": True,
                "message": f"Кнопка нажата, поле активировано, артикул {article} введен и {'товар выбран из списка' if locals().get('product_found', False) else 'подтвержден Enter'}",
                "user_id": user_id,
                "article": article,
                "screenshot": screenshot_path,
                "button_clicked": button_found,
                "primary_field_clicked": primary_field_found,
                "article_typed": field_found,
                "product_selected_from_list": locals().get('product_found', False)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка при клике и заполнении артикула: {e}")
            return {
                "success": False,
                "error": f"Исключение: {e}",
                "user_id": user_id,
                "article": article
            }

    async def get_available_warehouses(self, user_id: int) -> Dict[str, Any]:
        """
        Получает список доступных складов для перераспределения.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с результатом операции и списком складов
        """
        try:
            logger.info(f"🏪 Получение списка складов для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # Ищем поле "Выберите склад" и кликаем по нему
            warehouse_selectors = [
                "input[data-testid='warehouseFrom.Select_input_XuWs40d9v']",
                "input[data-testid*='warehouseFrom']",
                "input[data-testid*='warehouse']",
                "input[placeholder*='Выберите склад']",
                "input[placeholder*='склад']",
                ".warehouse-select input",
                "[data-testid*='Select_input'] input"
            ]
            
            warehouse_field_found = False
            for selector in warehouse_selectors:
                try:
                    logger.info(f"🔍 Поиск поля 'Выберите склад' по селектору: {selector}")
                    warehouse_field = await page.wait_for_selector(selector, timeout=2000)
                    if warehouse_field:
                        logger.info(f"✅ Найдено поле 'Выберите склад': {selector}")
                        await warehouse_field.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        await warehouse_field.click()
                        await asyncio.sleep(0.3)  # Быстрое ожидание выпадающего списка
                        warehouse_field_found = True
                        break
                except Exception as e:
                    logger.debug(f"Поле склада не найдено по селектору {selector}: {e}")
                    continue
            
            if not warehouse_field_found:
                return {
                    "success": False,
                    "error": "Не найдено поле 'Выберите склад'",
                    "user_id": user_id
                }
            
            # Быстрое ожидание списка складов
            await asyncio.sleep(0.3)
            
            # Делаем скриншот после клика для отладки
            debug_screenshot = f"screenshots_{user_id}/warehouse_dropdown_opened.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=debug_screenshot)
            if not self.fast_mode:
                logger.info(f"📸 Скриншот после клика на поле склада: {debug_screenshot}")
            
            # Добавим отладочную информацию - найдем все элементы на странице (только в медленном режиме)
            if not self.fast_mode:
                logger.info("🔍 ОТЛАДКА: Поиск всех возможных элементов на странице...")
                all_buttons = await page.query_selector_all("button")
                all_divs = await page.query_selector_all("div")
                all_testids = await page.query_selector_all("[data-testid]")
                
                logger.info(f"📊 Статистика элементов: кнопки={len(all_buttons)}, divы={len(all_divs)}, с data-testid={len(all_testids)}")
                
                # Выводим первые 10 элементов с data-testid для анализа
                for i, element in enumerate(all_testids[:10]):
                    try:
                        testid = await element.get_attribute("data-testid")
                        text = await element.text_content()
                        tag = await element.evaluate("el => el.tagName")
                        logger.info(f"🔍 Элемент {i}: <{tag}> data-testid='{testid}' text='{text[:50] if text else ''}'")
                    except:
                        continue
            
            # Пробуем найти склады разными способами
            warehouses = []
            
            # МЕТОД 1: Поиск складов по точным CSS классам (на основе ваших скринов)
            warehouse_option_selectors = [
                # ТОЧНЫЕ СЕЛЕКТОРЫ на основе вашего примера (Краснодар + Электросталь)
                "button.Dropdown-option__wrWrbSdFN.Dropdown-option--warning_chLdehnDx",
                "button[class*='Dropdown-option__wrWrbSdFN'][class*='Dropdown-option--warning_chLdehnDx']",
                "button[class*='Dropdown-option__wrWrbSdFN'][class*='Dropdown-option--warning']",
                "button[class*='Dropdown-option__wrWrbSdFN']",
                
                # По data-testid (если есть)
                "button[data-testid*='Dropdown-option__wrWrbSdFN.Dropdown-option--warning']",
                "button[data-testid*='Dropdown-option__wrWrbSdFN']",
                "button[data-testid*='Dropdown-option--warning_chLdehnDx']",
                
                # Общие селекторы по классам
                "button[class*='Dropdown-option'][class*='warning']",
                "button[class*='Dropdown-option']",
                "[role='option']"
            ]
            
            for selector in warehouse_option_selectors:
                try:
                    logger.info(f"🔍 МЕТОД 1 - Поиск опций складов по селектору: {selector}")
                    warehouse_elements = await page.query_selector_all(selector)
                    logger.info(f"🔍 Найдено {len(warehouse_elements)} опций по селектору: {selector}")
                    
                    for i, element in enumerate(warehouse_elements):
                        try:
                            text_content = await element.text_content()
                            data_testid = await element.get_attribute("data-testid")
                            class_name = await element.get_attribute("class")
                            
                            if text_content and text_content.strip():
                                warehouse_info = {
                                    "id": f"warehouse_{i}",
                                    "name": text_content.strip(),
                                    "data_testid": data_testid,
                                    "class": class_name,
                                    "selector": selector
                                }
                                warehouses.append(warehouse_info)
                                logger.info(f"📦 Найден склад: {text_content.strip()} (testid: {data_testid})")
                        except Exception as e:
                            logger.debug(f"Ошибка при обработке элемента склада: {e}")
                            continue
                    
                    if warehouses:  # Если нашли склады, прекращаем поиск
                        break
                        
                except Exception as e:
                    logger.debug(f"Склады не найдены по селектору {selector}: {e}")
                    continue
            
            # МЕТОД 2: Поиск элементов ТОЛЬКО с CSS классами складов
            if not warehouses:
                logger.info("🔍 МЕТОД 2 - Поиск ТОЛЬКО элементов с CSS классами складов...")
                
                # Ищем только элементы с точными CSS классами складов
                warehouse_css_selectors = [
                    "button[class*='Dropdown-option__wrWrbSdFN'][class*='warning']",
                    "button[class*='Dropdown-option__wrWrbSdFN']",
                    "[class*='Dropdown-option__wrWrbSdFN'][class*='warning']",
                    "[class*='Dropdown-option__wrWrbSdFN']"
                ]
                
                found_warehouses = []
                for selector in warehouse_css_selectors:
                    try:
                        logger.info(f"🔍 МЕТОД 2 - Поиск по CSS селектору: {selector}")
                        elements = await page.query_selector_all(selector)
                        logger.info(f"🔍 Найдено {len(elements)} элементов по селектору {selector}")
                        
                        for element in elements:
                            try:
                                text_content = await element.text_content()
                                data_testid = await element.get_attribute("data-testid")
                                class_name = await element.get_attribute("class")
                                
                                if text_content and text_content.strip():
                                    text = text_content.strip()
                                    
                                    # ЖЕСТКИЙ ФИЛЬТР - исключаем все НЕ-склады
                                    excluded_words = [
                                        'товары', 'цены', 'поставки', 'заказы', 'аналитика', 
                                        'продвижение', 'menu', 'chips', 'component', 'кроме',
                                        'фильтры', 'отчеты', 'главная', 'отчеты', 'новости',
                                        'перераспределить', 'скачать', 'отмена', 'excel'
                                    ]
                                    
                                    # Проверяем, что это НЕ служебный элемент
                                    is_warehouse = True
                                    for word in excluded_words:
                                        if word.lower() in text.lower():
                                            is_warehouse = False
                                            break
                                    
                                    # Дополнительно проверяем длину (города обычно 3-20 символов)
                                    if is_warehouse and 3 <= len(text) <= 20:
                                        warehouse_info = {
                                            "id": f"warehouse_css_{len(found_warehouses)}",
                                            "name": text,
                                            "data_testid": data_testid,
                                            "class": class_name,
                                            "selector": selector,
                                            "css_found": True
                                        }
                                        found_warehouses.append(warehouse_info)
                                        logger.info(f"🏪 СКЛАД НАЙДЕН: '{text}' (CSS: {class_name})")
                            except Exception as e:
                                continue
                    except Exception as e:
                        logger.debug(f"Ошибка поиска по селектору {selector}: {e}")
                        continue
                
                warehouses = found_warehouses[:10]  # Ограничиваем до 10
                logger.info(f"🔍 МЕТОД 2 - Найдено {len(warehouses)} складов по CSS классам")
            
            # МЕТОД 3: Поиск в видимом выпадающем списке
            if not warehouses:
                logger.info("🔍 МЕТОД 3 - Поиск складов в видимом выпадающем списке...")
                
                # Пытаемся найти видимый выпадающий список
                dropdown_selectors = [
                    "[class*='dropdown'][style*='display: block']",
                    "[class*='dropdown']:not([style*='display: none'])",
                    "[class*='menu'][style*='display: block']",
                    "[role='listbox']",
                    "[role='menu']"
                ]
                
                for dropdown_selector in dropdown_selectors:
                    try:
                        dropdown = await page.query_selector(dropdown_selector)
                        if dropdown:
                            logger.info(f"🔍 Найден выпадающий список: {dropdown_selector}")
                            
                            # Ищем в этом списке элементы складов
                            warehouse_in_dropdown = await dropdown.query_selector_all("button[class*='Dropdown-option'], [class*='option'], button")
                            logger.info(f"🔍 В списке найдено {len(warehouse_in_dropdown)} элементов")
                            
                            for element in warehouse_in_dropdown:
                                try:
                                    text = await element.text_content()
                                    class_name = await element.get_attribute("class")
                                    data_testid = await element.get_attribute("data-testid")
                                    
                                    if (text and text.strip() and 
                                        len(text.strip()) >= 3 and len(text.strip()) <= 20 and
                                        class_name and 'Dropdown-option' in class_name):
                                        
                                        warehouse_info = {
                                            "id": f"warehouse_dropdown_{len(warehouses)}",
                                            "name": text.strip(),
                                            "data_testid": data_testid,
                                            "class": class_name,
                                            "selector": dropdown_selector,
                                            "dropdown_found": True
                                        }
                                        warehouses.append(warehouse_info)
                                        logger.info(f"🏪 СКЛАД В СПИСКЕ: '{text.strip()}' (CSS: {class_name})")
                                except Exception as e:
                                    continue
                            break
                    except Exception as e:
                        continue
                
                logger.info(f"🔍 МЕТОД 3 - Найдено {len(warehouses)} складов в выпадающем списке")
            
            # МЕТОД 4: Попробуем найти склады по часто встречающимся в WB паттернам
            if not warehouses:
                logger.info("🔍 МЕТОД 4 - Поиск складов по WB паттернам...")
                wb_patterns = [
                    # ТОЧНЫЙ СЕЛЕКТОР на основе вашего примера (Электросталь)
                    "button[data-testid='Dropdown-option__wrWrbSdFN.Dropdown-option--warning_chLdehnDx']",
                    
                    # Паттерны на основе структуры из вашего примера
                    "button[data-testid*='Dropdown-option__wrWrbSdFN.Dropdown-option--warning']",
                    "button[data-testid*='Dropdown-option__wrWrbSdFN.Dropdown-option--']",
                    "button[data-testid*='Dropdown-option__wrWrbSdFN']",
                    "button[data-testid*='Dropdown-option--warning_chLdehnDx']",
                    "button[data-testid*='Dropdown-option--warning']",
                    
                    # Общие паттерны WB (более широкие)
                    "button[data-testid*='Dropdown-option__'][data-testid*='Dropdown-option--']",
                    "[data-testid*='Dropdown-option__'][data-testid*='.']",
                    "button[data-testid*='Dropdown-option'][data-testid*='warning']",
                    "button[data-testid*='Dropdown-option'][data-testid*='error']",
                    "button[data-testid*='Dropdown-option'][data-testid*='success']",
                    "[data-testid*='option'][data-testid*='__'][data-testid*='.']",
                ]
                
                for pattern in wb_patterns:
                    try:
                        logger.info(f"🔍 МЕТОД 3 - Поиск по WB паттерну: {pattern}")
                        pattern_warehouses = await self.find_warehouses_by_pattern(page, pattern)
                        if pattern_warehouses:
                            warehouses.extend(pattern_warehouses)
                            logger.info(f"✅ МЕТОД 3 - Найдено {len(pattern_warehouses)} складов по паттерну")
                            break
                    except Exception as e:
                        logger.debug(f"Ошибка поиска по паттерну {pattern}: {e}")
                        continue
            
            if not warehouses:
                return {
                    "success": False,
                    "error": "Не найдены доступные склады в выпадающем списке",
                    "user_id": user_id
                }
            
            # ОТЛАДКА: Найдем ВСЕ элементы с классом Dropdown-option
            logger.info("🔍 ОТЛАДКА - Поиск ВСЕХ элементов с Dropdown-option...")
            all_dropdown_elements = await page.query_selector_all("[class*='Dropdown-option']")
            logger.info(f"🔍 ОТЛАДКА - Найдено {len(all_dropdown_elements)} элементов с Dropdown-option")
            
            for i, element in enumerate(all_dropdown_elements[:15]):  # Первые 15 для анализа
                try:
                    text = await element.text_content()
                    class_name = await element.get_attribute("class")
                    tag_name = await element.evaluate("el => el.tagName")
                    is_visible = await element.is_visible()
                    
                    logger.info(f"🔍 ЭЛЕМЕНТ {i}: <{tag_name}> '{text}' visible={is_visible} class='{class_name}'")
                    
                    # Проверяем, содержит ли класс нужные паттерны
                    if class_name and 'wrWrbSdFN' in class_name and 'warning' in class_name:
                        logger.info(f"🎯 ПОТЕНЦИАЛЬНЫЙ СКЛАД: '{text}' с нужными CSS классами!")
                except Exception as e:
                    continue
            
            # Делаем скриншот для отладки
            screenshot_path = f"screenshots_{user_id}/warehouses_list.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
            logger.info(f"📸 Скриншот списка складов: {screenshot_path}")
            
            return {
                "success": True,
                "warehouses": warehouses,
                "warehouse_count": len(warehouses),
                "screenshot": screenshot_path,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении списка складов: {e}")
            return {
                "success": False,
                "error": f"Ошибка получения складов: {str(e)}",
                "user_id": user_id
            }

    async def select_warehouse(self, user_id: int, warehouse_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Выбирает конкретный склад из списка.
        
        Args:
            user_id: ID пользователя
            warehouse_data: Данные склада для выбора
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"🎯 Выбор склада для пользователя {user_id}: {warehouse_data.get('name', 'Неизвестный')}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # ВАЖНО: сначала нужно открыть выпадающий список!
            logger.info(f"🔍 Сначала открываем выпадающий список складов...")
            
            # Селекторы для поля "Откуда забрать"
            source_field_selectors = [
                # Основной селектор с data-testid
                "div[data-testid='form-select-group'] label:has-text('Откуда забрать') + div input",
                "label[data-testid*='UBlcSLabel']:has-text('Откуда забрать') + div input",
                
                # Альтернативные селекторы
                "//label[contains(text(), 'Откуда забрать')]//following-sibling::div//input",
                "input[placeholder='Выберите склад']",
                
                # По структуре из скриншота
                "div.Form-select-group_FCBdFmJB1 label:has-text('Откуда забрать') + div input",
                
                # Поиск по частичному совпадению
                "[data-testid*='select'][data-testid*='group'] label:has-text('Откуда') + div input"
            ]
            
            field_clicked = False
            for selector in source_field_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath селектор
                        elements = await page.locator(selector).all()
                        if elements:
                            await elements[0].click()
                            field_clicked = True
                            logger.info(f"✅ Клик по полю 'Откуда забрать' (XPath): {selector}")
                            break
                    else:
                        # CSS селектор
                        element = await page.query_selector(selector)
                        if element:
                            await element.click()
                            field_clicked = True
                            logger.info(f"✅ Клик по полю 'Откуда забрать' (CSS): {selector}")
                            break
                except Exception as e:
                    logger.debug(f"Не удалось кликнуть по селектору {selector}: {e}")
                    continue
            
            if not field_clicked:
                logger.error(f"❌ Не удалось найти и кликнуть по полю 'Откуда забрать'")
                return {
                    "success": False,
                    "error": "Не удалось открыть список складов",
                    "user_id": user_id
                }
            
            # Ждем появления выпадающего списка
            await asyncio.sleep(0.5 if self.fast_mode else 1.0)
            
            # Ищем и кликаем по выбранному складу
            warehouse_name = warehouse_data.get('name', '')
            data_testid = warehouse_data.get('data_testid', '')
            
            # Составляем селекторы для поиска склада
            warehouse_click_selectors = []
            
            if data_testid:
                warehouse_click_selectors.append(f"[data-testid='{data_testid}']")
                warehouse_click_selectors.append(f"button[data-testid='{data_testid}']")
                warehouse_click_selectors.append(f"div[data-testid='{data_testid}']")
            
            if warehouse_name:
                warehouse_click_selectors.extend([
                    f"button:has-text('{warehouse_name}')",
                    f"div:has-text('{warehouse_name}')",
                    f"[data-testid*='option']:has-text('{warehouse_name}')",
                    # Специфичные для WB селекторы с текстом
                    f"button[data-testid*='Dropdown-option__wrWrbSdFN']:has-text('{warehouse_name}')",
                    f"button[data-testid*='Dropdown-option--warning']:has-text('{warehouse_name}')",
                    f"button[data-testid*='Dropdown-option']:has-text('{warehouse_name}')"
                ])
            
            # Общие селекторы как fallback (добавляем новые паттерны WB)
            warehouse_click_selectors.extend([
                "button[data-testid*='Dropdown-option__wrWrbSdFN.Dropdown-option--warning']",
                "button[data-testid*='Dropdown-option__wrWrbSdFN.Dropdown-option--']",
                "button[data-testid*='Dropdown-option__wrWrbSdFN']",
                "button[data-testid*='Dropdown-option--warning']",
                "button[data-testid*='Dropdown-option']",
                "div[data-testid*='Dropdown-option']",
                "[role='option']"
            ])
            
            warehouse_selected = False
            for selector in warehouse_click_selectors:
                try:
                    logger.info(f"🔍 Поиск склада для клика по селектору: {selector}")
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        try:
                            text_content = await element.text_content()
                            if warehouse_name and warehouse_name in text_content:
                                logger.info(f"✅ Найден склад для клика: {text_content}")
                                await element.scroll_into_view_if_needed()
                                await asyncio.sleep(0.05)
                                await element.click()
                                await asyncio.sleep(0.3)
                                warehouse_selected = True
                                logger.info(f"🎯 Склад выбран: {warehouse_name}")
                                break
                        except Exception as e:
                            logger.debug(f"Ошибка при клике по складу: {e}")
                            continue
                    
                    if warehouse_selected:
                        break
                        
                except Exception as e:
                    logger.debug(f"Склад не найден для клика по селектору {selector}: {e}")
                    continue
            
            if not warehouse_selected:
                # Склад не найден в выпадающем списке
                logger.warning(f"⚠️ Склад '{warehouse_name}' не найден в выпадающем списке!")
                return {
                    "success": False,
                    "error": f"Склад '{warehouse_name}' не найден в списке доступных складов на сайте WB",
                    "warehouse_not_in_list": True,  # Специальный флаг
                    "user_id": user_id
                }
            
            # Ждем обработки выбора склада и появления возможных ошибок
            await asyncio.sleep(1.5)  # Увеличиваем время ожидания для появления ошибок
            
            logger.info(f"🔍 НАЧИНАЕМ ПРОВЕРКУ ОШИБОК для пользователя {user_id} после выбора склада '{warehouse_name}'")
            
            # Проверяем на ошибки после выбора склада "откуда забрать"
            error_messages = []
            error_selectors = [
                # Основной селектор ошибки из скриншота (точный)
                "span.Form-select-input__error_0o5Vr-u",
                "span[class*='Form-select-input__error_0o5Vr-u']",
                
                # Альтернативные селекторы для ошибок формы
                "span.Form-select-input__error_Qp5MtLu", 
                "span[class*='Form-select-input__error']",
                
                # Общие селекторы ошибок
                "[class*='Form-select-input__error']",
                "[class*='error'][class*='form']",
                "[class*='error'][class*='select']",
                ".error-message",
                "[data-testid*='error']",
                
                # Поиск по тексту для надежности
                "//*[contains(text(), 'лимит')]",
                "//*[contains(text(), 'Дневной')]", 
                "//*[contains(text(), 'исчерпан')]",
                "//*[contains(text(), 'Переместите')]"
            ]
            
            logger.info("🔍 Проверка ошибок после выбора склада...")
            
            for selector in error_selectors:
                try:
                    # Определяем тип селектора
                    if selector.startswith("//"):
                        # XPath селектор
                        error_elements = await page.locator(f"xpath={selector}").all()
                    else:
                        # CSS селектор
                        error_elements = await page.query_selector_all(selector)
                    
                    for error_element in error_elements:
                        try:
                            if await error_element.is_visible():
                                # Получаем полный текст элемента
                                error_text = await error_element.text_content()
                                if error_text and error_text.strip():
                                    cleaned_error = error_text.strip()
                                    
                                    # Дополнительная проверка на содержимое ошибки
                                    if any(keyword in cleaned_error.lower() for keyword in ['ошибка', 'лимит', 'исчерпан', 'переместите', 'завтра', 'недоступ']):
                                        # Очищаем ошибку от лишнего текста (убираем "Откуда забрать", "Куда" и т.д.)
                                        clean_patterns = [
                                            "откуда забрать",
                                            "откуда забратьдневной",  # Слитно как в логах
                                            "куда перенести", 
                                            "куда переместить",
                                            "выберите склад",
                                            "склад:"
                                        ]
                                        
                                        final_error = cleaned_error
                                        for pattern in clean_patterns:
                                            final_error = final_error.replace(pattern, "").replace(pattern.title(), "").replace(pattern.upper(), "")
                                        
                                        # Убираем лишние пробелы
                                        final_error = " ".join(final_error.split())
                                        
                                        # Проверяем что ошибка не пустая и не слишком короткая
                                        if final_error and len(final_error) > 15:
                                            # Избегаем дублирования похожих ошибок
                                            is_duplicate = False
                                            for existing_error in error_messages:
                                                # Если новая ошибка содержится в существующей или наоборот
                                                if final_error in existing_error or existing_error in final_error:
                                                    is_duplicate = True
                                                    break
                                            
                                            if not is_duplicate:
                                                error_messages.append(final_error)
                                                logger.warning(f"⚠️ Найдена ошибка: {final_error}")
                        except Exception as e:
                            logger.debug(f"Ошибка при обработке элемента ошибки: {e}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Ошибка при поиске ошибок по селектору {selector}: {e}")
                    continue
            
            # Если ошибки не найдены стандартными селекторами, попробуем более широкий поиск
            if not error_messages:
                logger.info("🔍 Ошибки не найдены стандартными селекторами, расширенный поиск...")
                
                # Ищем любые элементы с текстом об ошибках/лимитах
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
                        # Ищем элементы по тексту
                        xpath_selector = f"//*[contains(translate(text(), 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'), '{term.lower()}')]"
                        elements = await page.locator(f"xpath={xpath_selector}").all()
                        
                        for element in elements:
                            try:
                                if await element.is_visible():
                                    text = await element.text_content()
                                    if text and text.strip() and len(text.strip()) > 10:  # Минимальная длина для осмысленного сообщения
                                        cleaned_text = text.strip()
                                        
                                        # Очищаем ошибку от лишнего текста
                                        clean_patterns = [
                                            "откуда забрать",
                                            "откуда забратьдневной",  # Слитно как в логах
                                            "куда перенести", 
                                            "куда переместить",
                                            "выберите склад",
                                            "склад:"
                                        ]
                                        
                                        final_error = cleaned_text
                                        for pattern in clean_patterns:
                                            final_error = final_error.replace(pattern, "").replace(pattern.title(), "").replace(pattern.upper(), "")
                                        
                                        # Убираем лишние пробелы
                                        final_error = " ".join(final_error.split())
                                        
                                        # Проверяем что ошибка не пустая и не слишком короткая
                                        if final_error and len(final_error) > 15:
                                            # Избегаем дублирования похожих ошибок
                                            is_duplicate = False
                                            for existing_error in error_messages:
                                                if final_error in existing_error or existing_error in final_error:
                                                    is_duplicate = True
                                                    break
                                            
                                            if not is_duplicate:
                                                error_messages.append(final_error)
                                                logger.warning(f"⚠️ Найдена ошибка расширенным поиском: {final_error}")
                                                break  # Берем первое релевантное сообщение
                            except Exception as e:
                                continue
                        
                        if error_messages:  # Если нашли, прекращаем поиск
                            break
                            
                    except Exception as e:
                        logger.debug(f"Ошибка расширенного поиска по термину '{term}': {e}")
                        continue
            
            logger.info(f"🎯 РЕЗУЛЬТАТ ПРОВЕРКИ ОШИБОК: найдено {len(error_messages)} ошибок")
            for i, msg in enumerate(error_messages, 1):
                logger.warning(f"  {i}. {msg}")
            
            # Если есть ошибки, возвращаем их для повторного выбора
            if error_messages:
                logger.error(f"⚠️ НАЙДЕНЫ ОШИБКИ НА СТРАНИЦЕ! Возвращаем need_retry=True")
                
                # Делаем скриншот с ошибкой
                error_screenshot_path = f"screenshots_{user_id}/warehouse_selection_error.png"
                if not self.fast_mode:
                    Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                    await page.screenshot(path=error_screenshot_path)
                
                return {
                    "success": False,
                    "error": "warehouse_selection_error",
                    "error_messages": error_messages,
                    "need_retry": True,
                    "warehouse": warehouse_data,
                    "screenshot": error_screenshot_path,
                    "user_id": user_id
                }
            else:
                logger.info("✅ ОШИБКИ НЕ НАЙДЕНЫ, склад выбран успешно")
            
            # Делаем скриншот после успешного выбора
            screenshot_path = f"screenshots_{user_id}/warehouse_selected.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
            logger.info(f"📸 Скриншот после выбора склада: {screenshot_path}")
            
            return {
                "success": True,
                "message": f"Склад '{warehouse_name}' успешно выбран",
                "warehouse": warehouse_data,
                "screenshot": screenshot_path,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выборе склада: {e}")
            return {
                "success": False,
                "error": f"Ошибка выбора склада: {str(e)}",
                "user_id": user_id
            }

    async def get_destination_warehouses(self, user_id: int) -> Dict[str, Any]:
        """
        Получает список доступных складов назначения ("Куда перенести").
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с результатом операции и списком складов
        """
        try:
            logger.info(f"🎯 Получение списка складов назначения для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # Ищем и кликаем поле "Куда переместить" (назначение)
            destination_field_selectors = [
                # ТОЧНЫЙ СЕЛЕКТОР с вашего скрина - поиск input под label "Куда переместить"
                '//label[@data-testid="UBlcSLabel--richGrey_m7PWeFd3w"][contains(text(), "Куда переместить")]//following-sibling::*//input',
                '//label[@data-testid="UBlcSLabel--richGrey_m7PWeFd3w"]//following-sibling::*//input',
                '//label[contains(@data-testid, "UBlcSLabel")][contains(text(), "Куда переместить")]//following-sibling::*//input',
                
                # Поиск по точному тексту "Куда переместить"
                '//div[contains(text(), "Куда переместить")]//following::input[1]',
                '//label[contains(text(), "Куда переместить")]//following::input[1]',
                '//span[contains(text(), "Куда переместить")]//following::input[1]',
                '//div[contains(text(), "Куда переместить")]//parent::*//input',
                '//div[contains(text(), "Куда переместить")]//ancestor::*//input',
                
                # Поиск второго поля (НЕ первого)
                '(//input[contains(@placeholder, "Выберите склад")])[2]',
                '(//input[contains(@placeholder, "склад")])[2]',
                
                # Оригинальные селекторы
                'input[data-testid="WarehouseToSelect_input_XUWsrd9Br"]',
                'input[data-testid*="WarehouseToSelect_input"]',
                'input[data-testid*="WarehouseToSelect"]',
                
                # Исключаем первое поле
                'input[placeholder*="Выберите склад"]:not([data-testid*="WarehouseFromSelect"])',
                'input[placeholder*="склад"]:not([data-testid*="From"])',
                '[data-testid*="warehouse"][data-testid*="select"]:not([data-testid*="From"])'
            ]
            
            destination_field_found = False
            for selector in destination_field_selectors:
                try:
                    logger.info(f"🔍 Поиск поля назначения по селектору: {selector}")
                    
                    # Проверяем, является ли селектор XPath
                    if selector.startswith('//') or selector.startswith('(//'):
                        # Используем XPath
                        try:
                            logger.info(f"🔍 Пробуем XPath: {selector}")
                            locator = page.locator(f"xpath={selector}")
                            
                            # Проверяем, есть ли элементы
                            count = await locator.count()
                            logger.info(f"🔍 XPath нашел {count} элементов")
                            
                            if count > 0:
                                field = locator.first
                                if await field.is_visible():
                                    await field.click()
                                    await asyncio.sleep(0.3)  # Быстрое ожидание открытия списка
                                    destination_field_found = True
                                    logger.info(f"✅ Поле назначения найдено и нажато (XPath): {selector}")
                                    break
                                else:
                                    logger.debug(f"XPath элемент не видим: {selector}")
                            else:
                                logger.debug(f"XPath не нашел элементов: {selector}")
                        except Exception as xpath_e:
                            logger.debug(f"Ошибка XPath {selector}: {xpath_e}")
                            continue
                    else:
                        # Используем CSS селектор
                        try:
                            field = await page.wait_for_selector(selector, timeout=1500)
                            if field and await field.is_visible():
                                await field.click()
                                await asyncio.sleep(0.3)  # Быстрое ожидание открытия списка
                                destination_field_found = True
                                logger.info(f"✅ Поле назначения найдено и нажато (CSS): {selector}")
                                break
                            else:
                                logger.debug(f"CSS селектор не найден или не видим: {selector}")
                        except Exception as css_e:
                            logger.debug(f"Ошибка CSS {selector}: {css_e}")
                            continue
                except Exception as e:
                    logger.debug(f"Поле назначения не найдено по селектору {selector}: {e}")
                    continue
            
            if not destination_field_found:
                logger.warning("⚠️ Поле 'Выберите склад' (назначение) не найдено")
                screenshot_path = f"screenshots_{user_id}/no_destination_field.png"
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
                return {
                    "success": False,
                    "error": "Поле 'Выберите склад' для назначения не найдено",
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
            
            # Быстрое ожидание выпадающего списка
            await asyncio.sleep(0.3)
            
            # ОТЛАДКА: Ищем все поля "Выберите склад" на странице (только в медленном режиме)
            if not self.fast_mode:
                logger.info("🔍 ОТЛАДКА - Поиск всех полей 'Выберите склад' на странице...")
                all_select_fields = await page.query_selector_all('input[placeholder*="Выберите склад"], input[placeholder*="склад"]')
                logger.info(f"🔍 Найдено {len(all_select_fields)} полей 'Выберите склад'")
                
                for i, field in enumerate(all_select_fields):
                    try:
                        placeholder = await field.get_attribute("placeholder")
                        data_testid = await field.get_attribute("data-testid")
                        is_visible = await field.is_visible()
                        logger.info(f"📝 ПОЛЕ {i}: placeholder='{placeholder}' testid='{data_testid}' visible={is_visible}")
                    except Exception as e:
                        continue
                
                # ОТЛАДКА: Ищем все элементы с текстом "Куда"
                logger.info("🔍 ОТЛАДКА - Поиск всех элементов с текстом 'Куда'...")
                all_kuda_elements = await page.query_selector_all('*')
                kuda_count = 0
                for element in all_kuda_elements:
                    try:
                        text = await element.text_content()
                        if text and 'куда' in text.lower():
                            tag_name = await element.evaluate("el => el.tagName")
                            data_testid = await element.get_attribute("data-testid")
                            is_visible = await element.is_visible()
                            logger.info(f"🎯 КУДА ЭЛЕМЕНТ: <{tag_name}> '{text}' testid='{data_testid}' visible={is_visible}")
                            kuda_count += 1
                            if kuda_count >= 10:  # Ограничиваем вывод
                                break
                    except Exception as e:
                        continue
            
            # Используем ту же логику поиска складов
            warehouses = []
            
            # Поиск складов по точным CSS классам
            warehouse_option_selectors = [
                "button.Dropdown-option__wrWrbSdFN.Dropdown-option--warning_chLdehnDx",
                "button[class*='Dropdown-option__wrWrbSdFN'][class*='Dropdown-option--warning_chLdehnDx']",
                "button[class*='Dropdown-option__wrWrbSdFN'][class*='Dropdown-option--warning']",
                "button[class*='Dropdown-option__wrWrbSdFN']",
                "button[class*='Dropdown-option'][class*='warning']",
                "button[class*='Dropdown-option']",
                "[role='option']"
            ]
            
            for selector in warehouse_option_selectors:
                try:
                    logger.info(f"🔍 Поиск складов назначения по селектору: {selector}")
                    warehouse_elements = await page.query_selector_all(selector)
                    logger.info(f"🔍 Найдено {len(warehouse_elements)} элементов")
                    
                    for element in warehouse_elements:
                        try:
                            text_content = await element.text_content()
                            data_testid = await element.get_attribute("data-testid")
                            class_name = await element.get_attribute("class")
                            is_visible = await element.is_visible()
                            
                            if text_content and text_content.strip() and is_visible:
                                text = text_content.strip()
                                
                                # Фильтрация - исключаем служебные элементы
                                excluded_words = [
                                    'товары', 'цены', 'поставки', 'заказы', 'аналитика', 
                                    'продвижение', 'menu', 'chips', 'component', 'кроме',
                                    'фильтры', 'отчеты', 'главная', 'новости',
                                    'перераспределить', 'скачать', 'отмена', 'excel'
                                ]
                                
                                is_warehouse = True
                                for word in excluded_words:
                                    if word.lower() in text.lower():
                                        is_warehouse = False
                                        break
                                
                                if is_warehouse and 3 <= len(text) <= 30:
                                    warehouse_info = {
                                        "id": f"destination_warehouse_{len(warehouses)}",
                                        "name": text,
                                        "data_testid": data_testid,
                                        "class": class_name,
                                        "selector": selector
                                    }
                                    warehouses.append(warehouse_info)
                                    logger.info(f"🏪 СКЛАД НАЗНАЧЕНИЯ: '{text}' (CSS: {class_name})")
                        except Exception as e:
                            continue
                    
                    if warehouses:  # Если нашли склады, прекращаем поиск
                        break
                        
                except Exception as e:
                    logger.debug(f"Склады назначения не найдены по селектору {selector}: {e}")
                    continue
            
            # Делаем скриншот для отладки
            screenshot_path = f"screenshots_{user_id}/destination_warehouses_list.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
            logger.info(f"📸 Скриншот списка складов назначения: {screenshot_path}")
            
            if not warehouses:
                return {
                    "success": False,
                    "error": "Не найдены доступные склады назначения в выпадающем списке",
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
            
            return {
                "success": True,
                "warehouses": warehouses,
                "warehouse_count": len(warehouses),
                "user_id": user_id,
                "screenshot": screenshot_path
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка складов назначения для пользователя {user_id}: {e}")
            return {
                "success": False,
                "error": f"Ошибка при получении складов назначения: {str(e)}",
                "user_id": user_id
            }

    async def select_destination_warehouse(self, user_id: int, warehouse_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выбирает конкретный склад назначения из списка и проверяет ошибки.
        
        Args:
            user_id: ID пользователя
            warehouse_data: Данные склада назначения для выбора
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"🎯 Выбор склада назначения для пользователя {user_id}: {warehouse_data.get('name', 'Неизвестный')}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # СНАЧАЛА ОТКРЫВАЕМ ДРОПДАУН СКЛАДА НАЗНАЧЕНИЯ
            logger.info("🔽 Открываем дропдаун склада назначения...")
            
            # Селекторы для поля склада назначения (куда)
            destination_field_selectors = [
                "div[class*='Form-select-input']:has(label:has-text('Куда перенести'))",
                "div[class*='Form-select-input']:has(label:has-text('Куда переместить'))",
                "div[class*='Form-select-input']:has(label:has-text('Склад назначения'))",
                "[class*='Form-select-input']:nth-of-type(2)",  # Второе поле обычно назначение
                "[class*='Form-select-input']:last-of-type",    # Последнее поле
                "[class*='select']:has(label:has-text('Куда'))",
                "[class*='select']:has(label:has-text('назначения'))"
            ]
            
            dropdown_opened = False
            for field_selector in destination_field_selectors:
                try:
                    logger.info(f"🔍 Пробуем открыть дропдаун назначения по селектору: {field_selector}")
                    field = await page.query_selector(field_selector)
                    if field and await field.is_visible():
                        await field.click()
                        await asyncio.sleep(0.5)  # Даем время открыться
                        dropdown_opened = True
                        logger.info(f"✅ Дропдаун склада назначения открыт через: {field_selector}")
                        break
                except Exception as e:
                    logger.debug(f"Не удалось открыть дропдаун через {field_selector}: {e}")
                    continue
            
            if not dropdown_opened:
                logger.warning("⚠️ Не удалось открыть дропдаун склада назначения")
                # Попробуем общий подход
                try:
                    all_selects = await page.query_selector_all("[class*='Form-select-input'], [class*='select']")
                    if len(all_selects) >= 2:  # Второй селект должен быть назначением
                        await all_selects[1].click()
                        await asyncio.sleep(0.5)
                        logger.info("✅ Открыли второй дропдаун как склад назначения")
                        dropdown_opened = True
                except Exception as e:
                    logger.error(f"Ошибка при открытии второго дропдауна: {e}")
            
            # Ищем и кликаем по выбранному складу назначения
            warehouse_name = warehouse_data.get('name', '')
            
            # Составляем селекторы для поиска склада назначения
            warehouse_click_selectors = [
                f"button:has-text('{warehouse_name}')",
                f"button[class*='Dropdown-option']:has-text('{warehouse_name}')",
                f"button[class*='Dropdown-option__wrWrbSdFN']:has-text('{warehouse_name}')",
                "button[class*='Dropdown-option__wrWrbSdFN'][class*='warning']",
                "button[class*='Dropdown-option__wrWrbSdFN']",
                "button[class*='Dropdown-option']",
                "[role='option']"
            ]
            
            warehouse_selected = False
            for selector in warehouse_click_selectors:
                try:
                    logger.info(f"🔍 Поиск склада назначения для клика по селектору: {selector}")
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        try:
                            element_text = await element.text_content()
                            if element_text and warehouse_name in element_text and await element.is_visible():
                                await element.click()
                                await asyncio.sleep(0.3)
                                warehouse_selected = True
                                logger.info(f"✅ Склад назначения '{warehouse_name}' выбран успешно")
                                break
                        except Exception as e:
                            continue
                    
                    if warehouse_selected:
                        break
                        
                except Exception as e:
                    logger.debug(f"Ошибка при поиске склада назначения по селектору {selector}: {e}")
                    continue
            
            if not warehouse_selected:
                logger.warning(f"⚠️ Склад назначения '{warehouse_name}' не найден в выпадающем списке!")
                screenshot_path = f"screenshots_{user_id}/destination_warehouse_not_selected.png"
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
                return {
                    "success": False,
                    "error": f"Склад назначения '{warehouse_name}' не найден в списке доступных складов на сайте WB",
                    "warehouse_not_in_list": True,  # Специальный флаг
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
            
            # Ждем обработки выбора
            await asyncio.sleep(0.3)
            
            # Проверяем на ошибки
            error_result = await self.check_redistribution_errors(user_id)
            if not error_result["success"]:
                return error_result
            
            # Делаем финальный скриншот
            screenshot_path = f"screenshots_{user_id}/destination_warehouse_selected.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
            
            return {
                "success": True,
                "message": f"Склад назначения '{warehouse_name}' выбран успешно",
                "warehouse_name": warehouse_name,
                "user_id": user_id,
                "screenshot": screenshot_path
            }
            
        except Exception as e:
            logger.error(f"Ошибка при выборе склада назначения для пользователя {user_id}: {e}")
            return {
                "success": False,
                "error": f"Ошибка при выборе склада назначения: {str(e)}",
                "user_id": user_id
            }

    async def check_redistribution_errors(self, user_id: int) -> Dict[str, Any]:
        """
        Проверяет наличие ошибок на странице перераспределения.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с результатом проверки
        """
        try:
            logger.info(f"🔍 Проверка ошибок перераспределения для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # Ищем ошибки на странице
            error_selectors = [
                # ТОЧНЫЙ СЕЛЕКТОР с вашего скрина
                'span.Form-select-input__error_Qp5MtLu',
                'span[class*="Form-select-input__error"]',
                'span[class*="error"]',
                
                # Общие селекторы ошибок
                '.error',
                '[class*="error"]',
                '.alert-danger',
                '.validation-error',
                '[role="alert"]'
            ]
            
            errors_found = []
            for selector in error_selectors:
                try:
                    error_elements = await page.query_selector_all(selector)
                    for element in error_elements:
                        try:
                            error_text = await element.text_content()
                            is_visible = await element.is_visible()
                            
                            if error_text and error_text.strip() and is_visible:
                                errors_found.append(error_text.strip())
                                logger.warning(f"🚨 ОШИБКА НАЙДЕНА: {error_text.strip()}")
                        except Exception as e:
                            continue
                except Exception as e:
                    continue
            
            if errors_found:
                # Делаем скриншот ошибки
                screenshot_path = f"screenshots_{user_id}/redistribution_error.png"
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
                
                return {
                    "success": False,
                    "error": "Ошибка при перераспределении",
                    "error_messages": errors_found,
                    "user_id": user_id,
                    "screenshot": screenshot_path,
                    "need_retry": True  # Флаг для повторного выбора
                }
            
            return {
                "success": True,
                "message": "Ошибки не найдены",
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Ошибка при проверке ошибок перераспределения для пользователя {user_id}: {e}")
            return {
                "success": False,
                "error": f"Ошибка при проверке ошибок: {str(e)}",
                "user_id": user_id
            }

    async def close_and_reopen_redistribution(self, user_id: int, article: str) -> Dict[str, Any]:
        """
        Закрывает текущую форму распределения и открывает заново.
        Используется когда склад не найден в списке.
        """
        try:
            logger.info(f"🔄 Закрываем и переоткрываем форму распределения для пользователя {user_id}")
            
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # 1. Закрываем текущую форму - кликаем по кнопке закрытия
            close_button_selectors = [
                # По пути из скриншота
                "span.Button-link_icon_recZqdV\\+k",
                "[class*='Button-link_icon_recZqdV']",
                
                # Альтернативные селекторы
                "button[aria-label='Закрыть']",
                "button[aria-label='Close']",
                "[class*='close-button']",
                "[class*='Button-link_icon']",
                
                # XPath для поиска кнопки с крестиком
                "//button[contains(@class, 'Button-link_icon')]",
                "//span[contains(@class, 'Button-link_icon')]"
            ]
            
            close_clicked = False
            for selector in close_button_selectors:
                try:
                    if selector.startswith("//"):
                        elements = await page.locator(selector).all()
                        if elements:
                            await elements[0].click()
                            close_clicked = True
                            logger.info(f"✅ Закрыта форма распределения (XPath): {selector}")
                            break
                    else:
                        element = await page.query_selector(selector)
                        if element:
                            await element.click()
                            close_clicked = True
                            logger.info(f"✅ Закрыта форма распределения (CSS): {selector}")
                            break
                except Exception as e:
                    logger.debug(f"Не удалось закрыть по селектору {selector}: {e}")
                    continue
            
            if not close_clicked:
                logger.warning("⚠️ Не удалось найти кнопку закрытия формы")
            else:
                # Ждем закрытия формы
                await asyncio.sleep(0.5 if self.fast_mode else 1.0)
            
            # 2. Открываем заново форму распределения
            await self.open_redistribution_page(user_id)
            
            # 3. Заново вводим артикул
            await self.click_redistribution_menu_and_fill_article(user_id, article)
            
            return {
                "success": True,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка при переоткрытии формы: {e}")
            return {
                "success": False,
                "error": f"Ошибка при переоткрытии формы: {str(e)}",
                "user_id": user_id
            }
    
    async def get_available_quantity(self, user_id: int) -> Dict[str, Any]:
        """
        Получает доступное количество товара на складе.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с количеством товара
        """
        try:
            logger.info(f"📊 Получение количества товара для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # Ищем строку с количеством товара
            quantity_selectors = [
                # На основе вашего скрина
                'span[data-testid*="DIZZWUs"][data-testid*="text-h5_qhelTCwQq"][data-testid*="text-grey700_8a-rf7r3Qj"]',
                'span[data-testid*="DIZZWUs"]',
                'span[data-testid*="text-h5"]',
                
                # Поиск по тексту
                '//span[contains(text(), "Товара на складе")]',
                '//div[contains(text(), "Товара на складе")]',
                '//span[contains(text(), "шт")]',
                '//div[contains(text(), "шт")]',
                
                # Общие селекторы
                'span[class*="text-h5"]',
                'div[class*="quantity"]',
                '[data-testid*="quantity"]'
            ]
            
            quantity_text = None
            quantity_number = None
            
            for selector in quantity_selectors:
                try:
                    logger.info(f"🔍 Поиск количества по селектору: {selector}")
                    
                    if selector.startswith('//'):
                        # XPath
                        locator = page.locator(f"xpath={selector}")
                        count = await locator.count()
                        if count > 0:
                            element = locator.first
                            if await element.is_visible():
                                text = await element.text_content()
                                if text and text.strip():
                                    quantity_text = text.strip()
                                    logger.info(f"📊 Найден текст количества (XPath): '{quantity_text}'")
                                    break
                    else:
                        # CSS
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            if await element.is_visible():
                                text = await element.text_content()
                                if text and text.strip() and ('шт' in text or 'товар' in text.lower()):
                                    quantity_text = text.strip()
                                    logger.info(f"📊 Найден текст количества (CSS): '{quantity_text}'")
                                    break
                        
                        if quantity_text:
                            break
                            
                except Exception as e:
                    logger.debug(f"Ошибка поиска количества по селектору {selector}: {e}")
                    continue
            
            # Извлекаем число из текста
            if quantity_text:
                import re
                # Ищем числа в тексте
                numbers = re.findall(r'\d+', quantity_text)
                if numbers:
                    quantity_number = int(numbers[0])  # Берем первое число
                    logger.info(f"📊 Извлечено количество: {quantity_number}")
            
            # Делаем скриншот для отладки
            screenshot_path = f"screenshots_{user_id}/quantity_info.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
            
            if quantity_text:
                return {
                    "success": True,
                    "quantity_text": quantity_text,
                    "quantity_number": quantity_number,
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
            else:
                return {
                    "success": False,
                    "error": "Не удалось найти информацию о количестве товара",
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении количества товара для пользователя {user_id}: {e}")
            return {
                "success": False,
                "error": f"Ошибка при получении количества: {str(e)}",
                "user_id": user_id
            }

    async def input_quantity(self, user_id: int, quantity: int) -> Dict[str, Any]:
        """
        Вводит количество товара для перемещения.
        
        Args:
            user_id: ID пользователя
            quantity: Количество для ввода
            
        Returns:
            Dict с результатом операции
        """
        try:
            logger.info(f"📝 Ввод количества {quantity} для пользователя {user_id}")
            
            # Получаем браузер пользователя
            browser = await self.browser_manager.get_browser(user_id, headless=False, debug_mode=True)
            if not browser:
                return {
                    "success": False,
                    "error": "Не удалось получить браузер пользователя",
                    "user_id": user_id
                }
            
            page = browser.page
            if not page:
                return {
                    "success": False,
                    "error": "Страница браузера недоступна",
                    "user_id": user_id
                }
            
            # Ищем поле для ввода количества
            quantity_input_selectors = [
                # ТОЧНЫЙ СЕЛЕКТОР с вашего скрина
                'input[data-testid="quantity.simple-input_field_v62ZsG-3M"]',
                'input[data-testid*="quantity.simple-input_field"]',
                'input[data-testid*="quantity"]',
                
                # Поиск по placeholder
                'input[placeholder*="количество"]',
                'input[placeholder*="Укажите"]',
                'input[placeholder*="Введите"]',
                
                # По типу
                'input[type="number"]',
                'input[inputmode="numeric"]',
                
                # По классам
                'input[class*="quantity"]',
                'input[class*="input"]',
                'input[class*="field"]',
                
                # По data-testid
                '[data-testid*="input_field"]',
                '[data-testid*="input"]',
                '[data-testid*="field"]',
                
                # Общие input в форме
                'form input',
                'div[class*="form"] input',
                'div[class*="Form"] input',
                
                # Последний input на странице (часто поле количества)
                'input:last-of-type',
                
                # Input который виден и не disabled
                'input:not([disabled]):not([readonly])'
            ]
            
            quantity_input_found = False
            for selector in quantity_input_selectors:
                try:
                    logger.info(f"🔍 Поиск поля количества по селектору: {selector}")
                    field = await page.query_selector(selector)
                    if field and await field.is_visible():
                        # Очищаем поле и вводим количество
                        await field.click()
                        await asyncio.sleep(0.1)
                        
                        # Выделяем всё и удаляем
                        await field.press("Control+a")
                        await asyncio.sleep(0.05)
                        await field.press("Delete")
                        await asyncio.sleep(0.05)
                        
                        # Вводим новое количество
                        await field.type(str(quantity), delay=70)
                        await asyncio.sleep(0.1)
                        
                        # Проверяем, что значение введено
                        entered_value = await field.input_value()
                        if str(quantity) in str(entered_value):
                            quantity_input_found = True
                            logger.info(f"✅ Количество {quantity} введено в поле: {selector}")
                            break
                        
                except Exception as e:
                    logger.debug(f"Поле количества не найдено по селектору {selector}: {e}")
                    continue
            
            if not quantity_input_found:
                logger.warning("⚠️ Стандартные селекторы не сработали, пробуем альтернативный метод...")
                
                # АЛЬТЕРНАТИВНЫЙ МЕТОД: Найдем ВСЕ input элементы и попробуем каждый
                try:
                    all_inputs = await page.query_selector_all('input')
                    logger.info(f"🔍 Найдено {len(all_inputs)} input элементов на странице")
                    
                    for i, input_field in enumerate(all_inputs):
                        try:
                            # Проверяем, видимо ли поле
                            if not await input_field.is_visible():
                                continue
                            
                            # Получаем атрибуты поля
                            placeholder = await input_field.get_attribute('placeholder') or ""
                            input_type = await input_field.get_attribute('type') or ""
                            data_testid = await input_field.get_attribute('data-testid') or ""
                            class_name = await input_field.get_attribute('class') or ""
                            
                            logger.info(f"🔍 Input #{i}: type='{input_type}', placeholder='{placeholder}', testid='{data_testid}', class='{class_name}'")
                            
                            # Проверяем, похоже ли это на поле количества
                            is_quantity_field = (
                                'количество' in placeholder.lower() or
                                'quantity' in placeholder.lower() or
                                'quantity' in data_testid.lower() or
                                'количество' in class_name.lower() or
                                input_type == 'number' or
                                'numeric' in (await input_field.get_attribute('inputmode') or "")
                            )
                            
                            if is_quantity_field or i >= len(all_inputs) - 3:  # Пробуем последние 3 поля
                                logger.info(f"🎯 Пробуем input #{i} как поле количества...")
                                
                                # Пробуем ввести количество
                                await input_field.click()
                                await asyncio.sleep(0.1)
                                
                                # Очищаем поле
                                await input_field.press("Control+a")
                                await asyncio.sleep(0.05)
                                await input_field.press("Delete")
                                await asyncio.sleep(0.05)
                                
                                # Вводим количество
                                await input_field.type(str(quantity), delay=70)
                                await asyncio.sleep(0.1)
                                
                                # Проверяем, что значение введено
                                entered_value = await input_field.input_value()
                                if str(quantity) in str(entered_value):
                                    quantity_input_found = True
                                    logger.info(f"✅ Количество {quantity} успешно введено в input #{i}!")
                                    break
                                
                        except Exception as e:
                            logger.debug(f"Ошибка при попытке ввода в input #{i}: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Ошибка при альтернативном поиске полей: {e}")
            
            if not quantity_input_found:
                # Делаем скриншот для отладки
                screenshot_path = f"screenshots_{user_id}/no_quantity_field.png"
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
                
                return {
                    "success": False,
                    "error": "Поле для ввода количества не найдено",
                    "user_id": user_id,
                    "screenshot": screenshot_path
                }
            
            # Делаем финальный скриншот
            screenshot_path = f"screenshots_{user_id}/quantity_entered.png"
            if not self.fast_mode:
                Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                await page.screenshot(path=screenshot_path)
            
            # После ввода количества нажимаем кнопку "Перераспределить"
            await asyncio.sleep(0.3)  # Даем время на обработку ввода
            
            redistribute_button_selectors = [
                # ТОЧНЫЙ СЕЛЕКТОР с вашего скрина
                'button[data-testid="btg9qhQ8z1m__qenrv+npHf"]',
                'button[data-testid*="btg9qhQ8z1m"]',
                'button[data-testid*="qenrv+npHf"]',
                
                # Поиск по тексту
                'button:has-text("Перераспределить")',
                'button:has-text("перераспределить")',
                '[role="button"]:has-text("Перераспределить")',
                
                # Общие селекторы кнопок
                'button[class*="button"]',
                'button[type="submit"]',
                'button[class*="primary"]'
            ]
            
            redistribute_clicked = False
            for selector in redistribute_button_selectors:
                try:
                    logger.info(f"🔍 Поиск кнопки 'Перераспределить' по селектору: {selector}")
                    
                    if selector.startswith('button:has-text') or selector.startswith('[role="button"]:has-text'):
                        # Поиск по тексту
                        buttons = await page.query_selector_all('button, [role="button"]')
                        for button in buttons:
                            try:
                                button_text = await button.text_content()
                                if button_text and 'перераспределить' in button_text.lower() and await button.is_visible():
                                    await button.click()
                                    await asyncio.sleep(0.3)
                                    redistribute_clicked = True
                                    logger.info(f"✅ Кнопка 'Перераспределить' нажата: '{button_text}'")
                                    break
                            except Exception as e:
                                continue
                    else:
                        # Обычный селектор
                        button = await page.wait_for_selector(selector, timeout=2000)
                        if button and await button.is_visible():
                            await button.click()
                            await asyncio.sleep(0.3)
                            redistribute_clicked = True
                            logger.info(f"✅ Кнопка 'Перераспределить' нажата по селектору: {selector}")
                            break
                    
                    if redistribute_clicked:
                        break
                        
                except Exception as e:
                    logger.debug(f"Кнопка 'Перераспределить' не найдена по селектору {selector}: {e}")
                    continue
            
            # Делаем финальный скриншот
            final_screenshot_path = f"screenshots_{user_id}/redistribution_completed.png"
            await page.screenshot(path=final_screenshot_path)
            
            if redistribute_clicked:
                return {
                    "success": True,
                    "message": f"Количество {quantity} введено и перераспределение запущено",
                    "quantity": quantity,
                    "user_id": user_id,
                    "screenshot": final_screenshot_path,
                    "redistribute_clicked": True
                }
            else:
                logger.warning("⚠️ Кнопка 'Перераспределить' не найдена")
                return {
                    "success": True,
                    "message": f"Количество {quantity} введено успешно, но кнопка 'Перераспределить' не найдена",
                    "quantity": quantity,
                    "user_id": user_id,
                    "screenshot": final_screenshot_path,
                    "redistribute_clicked": False,
                    "warning": "Кнопка 'Перераспределить' не найдена - завершите вручную"
                }
            
        except Exception as e:
            logger.error(f"Ошибка при вводе количества для пользователя {user_id}: {e}")
            return {
                "success": False,
                "error": f"Ошибка при вводе количества: {str(e)}",
                "user_id": user_id
            }


# Глобальный экземпляр сервиса
redistribution_service = None

def get_redistribution_service(browser_manager: BrowserManager, fast_mode: bool = True) -> WBRedistributionService:
    """Получить экземпляр сервиса перераспределения."""
    global redistribution_service
    if redistribution_service is None:
        redistribution_service = WBRedistributionService(browser_manager, fast_mode)
    return redistribution_service
