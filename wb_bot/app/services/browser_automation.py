#!/usr/bin/env python3
"""
Профессиональная браузерная автоматизация для WB на Playwright.
Обход детекции, стелс режим, полный контроль.
"""

import asyncio
import json
import random
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import playwright_stealth
from ..utils.logger import get_logger
from .database_service import db_service

logger = get_logger(__name__)


class WBBrowserAutomationPro:
    """Профессиональная автоматизация браузера для WB с обходом детекции."""
    
    def __init__(self, headless: bool = True, debug_mode: bool = False, user_id: int = None, browser_type: str = "firefox"):
        # В production ВСЕГДА headless (нет графического окружения в Railway)
        import os
        environment = os.getenv("ENVIRONMENT", "development").lower()
        self.headless = True if environment == "production" else headless
        self.debug_mode = debug_mode
        self.user_id = user_id
        self.browser_type = browser_type  # "chromium", "firefox", "webkit"
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # МУЛЬТИБРАУЗЕРНАЯ ИЗОЛЯЦИЯ! Каждый браузер = уникальные файлы и порты  
        if user_id:
            self.cookies_file = Path(f"wb_cookies_{user_id}.json")
            self.user_data_dir = Path(f"wb_user_data_{user_id}")
            self.screenshots_dir = Path(f"screenshots_{user_id}")
            # КРИТИЧНО: уникальные порты! ХЕШИРУЕМ user_id чтобы получить число 0-999
            self.port_offset = hash(str(user_id)) % 1000  # Хеш даст число 0-999
            self.debug_port = 9222 + self.port_offset  # Порты 9222-10221
        else:
            self.cookies_file = Path("wb_cookies.json")
            self.user_data_dir = Path("wb_user_data")
            self.screenshots_dir = Path("screenshots")
            # Дефолтный порт для единственного браузера
            self.debug_port = 9222
            self.port_offset = 0
            
        # Создаем папки если их нет
        self.user_data_dir.mkdir(exist_ok=True)
        self.screenshots_dir.mkdir(exist_ok=True)
        
        if user_id:
            logger.info(f"🔐 Мультибраузер: пользователь {user_id}, порт {self.debug_port} (offset: {self.port_offset})")
            logger.info(f"📁 Данные: {self.user_data_dir}")
            logger.info(f"📸 Скриншоты: {self.screenshots_dir}")
        
        # Коды стран для правильного парсинга номеров
        self.country_codes = {
            '+7': {'name': 'Россия/Казахстан', 'digits': 10},
            '+996': {'name': 'Кыргызстан', 'digits': 9},
            '+998': {'name': 'Узбекистан', 'digits': 9},
            '+992': {'name': 'Таджикистан', 'digits': 9},
            '+993': {'name': 'Туркменистан', 'digits': 8},
            '+994': {'name': 'Азербайджан', 'digits': 9},
            '+995': {'name': 'Грузия', 'digits': 9},
            '+374': {'name': 'Армения', 'digits': 8},
            '+375': {'name': 'Беларусь', 'digits': 9},
            '+380': {'name': 'Украина', 'digits': 9},
            '+1': {'name': 'США/Канада', 'digits': 10},
            '+44': {'name': 'Великобритания', 'digits': 10},
            '+49': {'name': 'Германия', 'digits': 10},
            '+33': {'name': 'Франция', 'digits': 9},
            '+39': {'name': 'Италия', 'digits': 10},
            '+34': {'name': 'Испания', 'digits': 9},
            '+86': {'name': 'Китай', 'digits': 11},
            '+81': {'name': 'Япония', 'digits': 10},
            '+82': {'name': 'Южная Корея', 'digits': 10},
            '+91': {'name': 'Индия', 'digits': 10},
        }
        
        # Настройки для обхода детекции
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        
        # Реальные viewport размеры
        self.viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864}
        ]
    
    def parse_phone_number(self, phone: str) -> Tuple[str, str, str]:
        """
        Охуенный парсер номеров телефонов для всех стран мира!
        
        Принимает любой формат номера и возвращает:
        - country_code: код страны (например, '+7', '+996')
        - clean_number: номер без кода страны (например, '9001234567')
        - country_name: название страны
        
        Примеры:
        '+79001234567' -> ('+7', '9001234567', 'Россия/Казахстан')
        '+996500441234' -> ('+996', '500441234', 'Кыргызстан')
        '79001234567' -> ('+7', '9001234567', 'Россия/Казахстан')
        '89001234567' -> ('+7', '9001234567', 'Россия/Казахстан')
        '+1234567890' -> ('+1', '234567890', 'США/Канада')
        """
        
        # Убираем все лишние символы (пробелы, тире, скобки)
        clean_phone = re.sub(r'[\s\-\(\)]+', '', phone.strip())
        logger.info(f"🔍 Парсинг номера: '{phone}' -> очищенный: '{clean_phone}'")
        
        # Если номер начинается с плюса
        if clean_phone.startswith('+'):
            # Ищем подходящий код страны
            for code, info in self.country_codes.items():
                if clean_phone.startswith(code):
                    country_code = code
                    clean_number = clean_phone[len(code):]
                    country_name = info['name']
                    
                    logger.info(f"✅ Определена страна: {country_name} ({country_code})")
                    logger.info(f"📱 Номер без кода: '{clean_number}'")
                    return country_code, clean_number, country_name
            
            # Если код не найден в нашей базе, берем первые 1-4 цифры как код
            match = re.match(r'\+(\d{1,4})(\d+)', clean_phone)
            if match:
                code_digits, number_part = match.groups()
                country_code = f"+{code_digits}"
                clean_number = number_part
                country_name = f"Неизвестная страна ({country_code})"
                
                logger.warning(f"⚠️ Неизвестный код страны: {country_code}")
                logger.info(f"📱 Номер без кода: '{clean_number}'")
                return country_code, clean_number, country_name
        
        # Если номер без плюса, пытаемся определить по первым цифрам
        elif clean_phone.isdigit():
            # Россия: номера начинающиеся с 7, 8, 9
            if clean_phone.startswith('7') and len(clean_phone) == 11:
                country_code = '+7'
                clean_number = clean_phone[1:]  # Убираем первую 7
                country_name = 'Россия/Казахстан'
                
            elif clean_phone.startswith('8') and len(clean_phone) == 11:
                country_code = '+7'
                clean_number = '9' + clean_phone[2:]  # 8 заменяем на 9
                country_name = 'Россия/Казахстан'
                
            elif clean_phone.startswith('9') and len(clean_phone) == 10:
                country_code = '+7'
                clean_number = clean_phone  # Уже без кода
                country_name = 'Россия/Казахстан'
                
            # Кыргызстан: 996 + 9 цифр
            elif clean_phone.startswith('996') and len(clean_phone) == 12:
                country_code = '+996'
                clean_number = clean_phone[3:]  # Убираем 996
                country_name = 'Кыргызстан'
                
            # США/Канада: 1 + 10 цифр
            elif clean_phone.startswith('1') and len(clean_phone) == 11:
                country_code = '+1'
                clean_number = clean_phone[1:]  # Убираем первую 1
                country_name = 'США/Канада'
                
            # Другие коды стран (998, 992, 993, etc.)
            else:
                for code, info in self.country_codes.items():
                    code_digits = code[1:]  # Убираем +
                    if clean_phone.startswith(code_digits):
                        expected_length = len(code_digits) + info['digits']
                        if len(clean_phone) == expected_length:
                            country_code = code
                            clean_number = clean_phone[len(code_digits):]
                            country_name = info['name']
                            break
                else:
                    # По умолчанию считаем что это Россия
                    country_code = '+7'
                    clean_number = clean_phone
                    country_name = 'Россия/Казахстан (по умолчанию)'
                    logger.warning(f"⚠️ Не удалось определить страну для номера '{clean_phone}', считаю что это Россия")
            
            logger.info(f"✅ Определена страна: {country_name} ({country_code})")
            logger.info(f"📱 Номер без кода: '{clean_number}'")
            return country_code, clean_number, country_name
        
        # Если ничего не подошло, возвращаем как есть
        logger.error(f"❌ Не удалось распарсить номер: '{phone}'")
        return '+7', clean_phone, 'Неопределенная страна'
    
    async def should_skip_login(self) -> bool:
        """Проверяет нужно ли пропустить авторизацию (если есть валидная сессия с cookies)."""
        if not self.user_id:
            return False
        
        try:
            logger.info(f"🔍 Проверяю необходимость авторизации для пользователя {self.user_id}")
            
            # ШАГ 1: Проверяем наличие cookies в БД
            cookies_json = await db_service.load_browser_cookies(self.user_id)
            if not cookies_json:
                logger.info(f"📭 Нет сохраненных cookies для пользователя {self.user_id} - требуется авторизация")
                await db_service.update_browser_session_valid(self.user_id, False)
                return False
            
            # ШАГ 2: Пробуем зайти на защищенную страницу WB с этими cookies
            if self.page and not self.page.is_closed():
                try:
                    logger.info("🌐 Проверяю валидность cookies на странице WB...")
                    
                    # Переходим на страницу управления поставками (требует авторизации)
                    await self.page.goto(
                        "https://seller.wildberries.ru/supplies-management/all-supplies", 
                        wait_until="networkidle", 
                        timeout=15000
                    )
                    await asyncio.sleep(2)
                    
                    current_url = self.page.url
                    logger.info(f"📍 Текущий URL: {current_url}")
                    
                    # Если редиректнуло на логин - cookies невалидны
                    if any([
                        'seller-auth.wildberries.ru' in current_url,
                        'auth' in current_url.lower(),
                        'login' in current_url.lower()
                    ]):
                        logger.info(f"❌ Cookies устарели для пользователя {self.user_id} (редирект на: {current_url})")
                        await db_service.update_browser_session_valid(self.user_id, False)
                        return False
                    
                    # Если остались на seller.wildberries.ru - авторизация валидна
                    if 'seller.wildberries.ru' in current_url:
                        logger.info(f"✅ Пользователь {self.user_id} АВТОРИЗОВАН! Cookies валидны.")
                        await db_service.update_browser_session_valid(self.user_id, True)
                        return True
                    
                    # Неизвестный URL - требуем авторизацию
                    logger.warning(f"⚠️ Неожиданный URL: {current_url}")
                    await db_service.update_browser_session_valid(self.user_id, False)
                    return False
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка проверки авторизации через браузер: {e}")
                    await db_service.update_browser_session_valid(self.user_id, False)
                    return False
            
            # Если браузер недоступен
            logger.warning("⚠️ Браузер недоступен для проверки cookies")
            return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии: {e}")
            return False
    
    async def start_browser(self, headless: bool = False) -> bool:
        """Запуск браузера с максимальным обходом детекции."""
        try:
            logger.info("🚀 Запускаю Playwright браузер...")
            
            self.playwright = await async_playwright().start()
            
            # Продвинутые настройки браузера для обхода детекции
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions-except=",
                "--disable-extensions",
                "--disable-plugins",
                f"--remote-debugging-port={self.debug_port}",  # УНИКАЛЬНЫЙ ПОРТ для каждого браузера!
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-field-trial-config",
                "--disable-back-forward-cache",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-translate",
                "--disable-ipc-flooding-protection",
                "--no-first-run",
                "--no-service-autorun",
                "--password-store=basic",
                "--use-mock-keychain",
                "--force-fieldtrials=*BackgroundTracing/default/",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-domain-reliability",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                "--disable-ipc-flooding-protection",
                "--enable-features=NetworkService,NetworkServiceInProcess",
                "--force-color-profile=srgb",
                "--metrics-recording-only",
                "--no-default-browser-check",
                "--no-pings",
                "--use-gl=swiftshader",
                "--window-size=1920,1080"
            ]
            
            if not self.headless:
                browser_args.extend([
                    "--start-maximized",
                    "--disable-web-security",
                    "--allow-running-insecure-content"
                ])
            
            # Создаем папку для пользовательских данных если не существует
            self.user_data_dir.mkdir(exist_ok=True)
            
            # ВЫБИРАЕМ БРАУЗЕР ПО ТИПУ - FIREFOX ЛУЧШЕ ДЛЯ ОБХОДА ДЕТЕКЦИИ WB!
            logger.info(f"🌐 Запускаю браузер: {self.browser_type.upper()}")
            
            if self.browser_type == "firefox":
                # FIREFOX - лучший для обхода детекции WB!
                firefox_prefs = {
                    "dom.webdriver.enabled": False,
                    "useAutomationExtension": False,
                    "general.useragent.override": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
                }
                
                self.browser = await self.playwright.firefox.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir),
                    headless=self.headless,
                    slow_mo=50 if self.debug_mode else 0,
                    devtools=self.debug_mode and not self.headless,
                    firefox_user_prefs=firefox_prefs,
                    viewport=random.choice(self.viewports),
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                    geolocation={"latitude": 55.7558, "longitude": 37.6176},
                    permissions=["geolocation"],
                    color_scheme="light",
                    java_script_enabled=True,
                    accept_downloads=True,
                    ignore_https_errors=True,
                    bypass_csp=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    }
                )
                
            elif self.browser_type == "webkit":
                # WEBKIT (Safari) - максимальный стелс!
                self.browser = await self.playwright.webkit.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir),
                    headless=self.headless,
                    slow_mo=50 if self.debug_mode else 0,
                    devtools=self.debug_mode and not self.headless,
                    viewport=random.choice(self.viewports),
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                    geolocation={"latitude": 55.7558, "longitude": 37.6176},
                    permissions=["geolocation"],
                    color_scheme="light",
                    java_script_enabled=True,
                    accept_downloads=True,
                    ignore_https_errors=True,
                    bypass_csp=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    }
                )
                
            else:  # chromium (fallback)
                # CHROMIUM - может детектироваться WB!
                logger.warning("⚠️ Используется Chromium - может быть обнаружен WB!")
                self.browser = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir),
                    headless=self.headless,
                    args=browser_args,
                    slow_mo=50 if self.debug_mode else 0,
                    devtools=self.debug_mode and not self.headless,
                    viewport=random.choice(self.viewports),
                    user_agent=random.choice(self.user_agents),
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                    geolocation={"latitude": 55.7558, "longitude": 37.6176},
                    permissions=["geolocation"],
                    color_scheme="light",
                    reduced_motion="no-preference",
                    forced_colors="none",
                    java_script_enabled=True,
                    accept_downloads=True,
                    ignore_https_errors=True,
                    bypass_csp=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Cache-Control": "max-age=0"
                    }
                )
            
            # При использовании launch_persistent_context, браузер И ЕСТЬ контекст
            self.context = self.browser
            
            # Создаем страницу
            logger.info(f"📄 СОЗДАЮ ГЛАВНУЮ СТРАНИЦУ для пользователя {self.user_id}")
            self.page = await self.context.new_page()
            
            # Применяем stealth режим для максимального обхода детекции
            stealth = playwright_stealth.Stealth()
            await stealth.apply_stealth_async(self.page)
            
            # Дополнительные скрипты для обхода детекции
            await self._inject_stealth_scripts()
            
            # Загружаем куки если есть
            await self._load_cookies()
            
            logger.info("✅ Браузер запущен успешно с полным обходом детекции")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска браузера: {e}")
            logger.error(f"❌ Тип ошибки: {type(e).__name__}")
            logger.error(f"❌ Детали: {str(e)}")
            import traceback
            logger.error(f"❌ Трассировка: {traceback.format_exc()}")
            await self.close_browser()
            return False
    
    async def _inject_stealth_scripts(self):
        """Инжектим дополнительные скрипты для обхода детекции."""
        stealth_scripts = [
            # Безопасно убираем webdriver property
            """
            try {
                if ('webdriver' in navigator) {
                    delete navigator.webdriver;
                }
            } catch (e) {
                navigator.webdriver = undefined;
            }
            """,
            
            # Фиксим permissions
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            """,
            
            # Фиксим plugins
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            """,
            
            # Фиксим languages
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
            });
            """,
            
            # Добавляем реальное поведение мыши
            """
            ['mousedown', 'mouseup', 'mousemove', 'mouseover', 'mouseout'].forEach(eventType => {
                document.addEventListener(eventType, function(e) {
                    e.isTrusted = true;
                }, true);
            });
            """
        ]
        
        for script in stealth_scripts:
            await self.page.add_init_script(script)
    
    async def _load_cookies(self):
        """ЗАГРУЖАЕМ КУКИ ТОЛЬКО ИЗ БД ДЛЯ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ."""
        cookies_loaded = False
        
        # Загружаем cookies ТОЛЬКО из БД для этого user_id
        if self.user_id:
            try:
                cookies_json = await db_service.load_browser_cookies(self.user_id)
                if cookies_json:
                    try:
                        cookies = json.loads(cookies_json)
                        await self.context.add_cookies(cookies)
                        logger.info(f"🍪 Куки загружены из БД для пользователя {self.user_id}")
                        cookies_loaded = True
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка парсинга куки из БД: {e}")
                else:
                    logger.info(f"📭 Нет сохраненных куки в БД для пользователя {self.user_id}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки куки из БД: {e}")
        else:
            logger.warning("⚠️ user_id не указан, пропускаем загрузку куки")
        
        if not cookies_loaded:
            logger.info(f"🔄 Куки не найдены для пользователя {self.user_id}, начинаем с чистой сессии")
    
    async def _save_cookies(self):
        """СОХРАНЯЕМ КУКИ ТОЛЬКО В БД ДЛЯ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ."""
        if not self.user_id:
            logger.warning("⚠️ user_id не указан, пропускаем сохранение куки")
            return
            
        try:
            cookies = await self.context.cookies()
            cookies_json = json.dumps(cookies, ensure_ascii=False)
            
            # Сохраняем ТОЛЬКО в БД
            success = await db_service.save_browser_cookies(self.user_id, cookies_json)
            if success:
                logger.info(f"💾 Куки сохранены в БД для пользователя {self.user_id}")
            else:
                logger.error(f"❌ Ошибка сохранения куки в БД для пользователя {self.user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения куки: {e}")
    
    async def _check_booking_success(self) -> Dict[str, Any]:
        """
        ПРОВЕРЯЕТ РЕЗУЛЬТАТ БРОНИРОВАНИЯ НА СТРАНИЦЕ WB.
        
        Возвращает:
        {
            "success": bool,  # Успешно ли бронирование
            "retry": bool,    # Нужна ли повторная попытка
            "message": str    # Сообщение о результате
        }
        """
        try:
            logger.info("🔍 Анализирую результат бронирования...")
            
            # БЛЯДЬ! Ждем НАМНОГО ДОЛЬШЕ для загрузки ответа от WB!
            await asyncio.sleep(10)  # УВЕЛИЧИЛ С 5 ДО 10 СЕКУНД!
            
            # ИНДИКАТОРЫ УСПЕХА (включая информационные сообщения после успешного бронирования)
            success_indicators = [
                # Основные сообщения об успехе
                'text="Поставка запланирована"',
                'text="Поставка забронирована"', 
                'text="Успешно"',
                'text="Бронирование выполнено"',
                'text="Дата выбрана"',
                
                # ИНФОРМАЦИОННЫЕ СООБЩЕНИЯ ПОСЛЕ УСПЕШНОГО БРОНИРОВАНИЯ
                'text*="Обратите внимание, чтобы без проблем совершить отгрузку"',
                'text*="сгенерировать и распечатать ШК коробов"',
                'text*="распределить товары по коробам"',
                'text*="оформить пропуск"',
                'text*="можете сделать это во вкладках"',
                'text*="Упаковка"',
                'text*="Пропуск"',
                
                # Классы успеха
                '[class*="success"]',
                '[class*="confirm"]',
                '.notification-success',
                '.success-message',
                
                # Конкретные селекторы WB
                '[data-testid*="success"]',
                '[data-testid*="confirm"]'
            ]
            
            # ИНДИКАТОРЫ ОШИБОК (НЕ ИНФОРМАЦИОННЫХ СООБЩЕНИЙ!)
            error_indicators = [
                # Основные сообщения об ошибках
                'text*="Нет доступных слотов"',
                'text*="Слот уже занят"',
                'text*="Дата недоступна"',
                'text*="Ошибка бронирования"',
                'text*="Не удалось забронировать"',
                'text*="Попробуйте позже"',
                'text*="Время истекло"',
                'text*="Превышено количество"',
                
                # Классы ТОЛЬКО критических ошибок
                '[class*="error"]:not([class*="info"]):not([class*="notice"])',
                '.notification-error',
                '.error-message',
                
                # Конкретные селекторы WB критических ошибок
                '[data-testid*="error"]:not([data-testid*="info"])'
            ]
            
            # ПРОВЕРЯЕМ УСПЕХ
            for indicator in success_indicators:
                try:
                    elements = self.page.locator(indicator)
                    count = await elements.count()
                    
                    if count > 0:
                        for i in range(count):
                            element = elements.nth(i)
                            if await element.is_visible():
                                text = await element.text_content()
                                logger.info(f"✅ Найден индикатор успеха: '{text}' через {indicator}")
                                return {
                                    "success": True,
                                    "retry": False,
                                    "message": f"🎉 Бронирование успешно: {text}"
                                }
                except Exception as e:
                    logger.debug(f"Ошибка проверки индикатора успеха {indicator}: {e}")
                    continue
            
            # ПРОВЕРЯЕМ ОШИБКИ
            for indicator in error_indicators:
                try:
                    elements = self.page.locator(indicator)
                    count = await elements.count()
                    
                    if count > 0:
                        for i in range(count):
                            element = elements.nth(i)
                            if await element.is_visible():
                                text = await element.text_content()
                                logger.warning(f"⚠️ Найден индикатор ошибки: '{text}' через {indicator}")
                                
                                # Определяем нужна ли повторная попытка
                                retry_keywords = ["попробуйте позже", "недоступна", "занят"]
                                should_retry = any(keyword in text.lower() for keyword in retry_keywords)
                                
                                return {
                                    "success": False,
                                    "retry": should_retry,
                                    "message": f"❌ Ошибка бронирования: {text}"
                                }
                except Exception as e:
                    logger.debug(f"Ошибка проверки индикатора ошибки {indicator}: {e}")
                    continue
            
            # ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ: изменилась ли страница
            try:
                # ПРОВЕРКА 1: Изменился ли URL (перенаправление после успешного бронирования)
                current_url = self.page.url
                logger.info(f"🔗 Текущий URL: {current_url}")
                
                # КРИТИЧНО: ПРОВЕРЯЕМ ИЗМЕНЕНИЕ SUPPLY ID В URL!
                # После успешного бронирования WB меняет supplyId в URL
                if "supplyId=" in current_url:
                    import re
                    url_supply_match = re.search(r'supplyId=(\d+)', current_url)
                    if url_supply_match:
                        url_supply_id = url_supply_match.group(1)
                        logger.info(f"🆔 НОВЫЙ SUPPLY ID В URL: {url_supply_id}")
                        return {
                            "success": True,
                            "retry": False,
                            "message": f"🎉 Бронирование успешно! Новый supply ID: {url_supply_id}"
                        }
                
                # Если URL содержит признаки успешного бронирования
                success_url_indicators = [
                    "supply-created", "booking-success", "planned", "scheduled", 
                    "success", "confirmed", "completed"
                ]
                
                for indicator in success_url_indicators:
                    if indicator in current_url.lower():
                        logger.info(f"✅ URL содержит индикатор успеха: {indicator}")
                        return {
                            "success": True,
                            "retry": False,
                            "message": f"🎉 Успешное перенаправление на страницу результата: {indicator}"
                        }
                
                # ПРОВЕРКА 2: Проверяем что модальное окно закрылось (признак завершения)
                modal_selectors = [
                    '[class*="calendar"]',
                    '[id*="Portal"]', 
                    '[role="dialog"]',
                    '[class*="Modal"]',
                    '[data-testid*="modal"]'
                ]
                
                modal_still_open = False
                for selector in modal_selectors:
                    try:
                        modal_count = await self.page.locator(selector).count()
                        if modal_count > 0:
                            modal_still_open = True
                            break
                    except:
                        continue
                
                if not modal_still_open:
                    logger.info("✅ Модальное окно закрылось - операция завершена")
                    return {
                        "success": True,
                        "retry": False,
                        "message": "🎉 Модальное окно закрылось - бронирование вероятно успешно"
                    }
                else:
                    logger.info("⏳ Модальное окно все еще открыто - ждем...")
                    
            except Exception as e:
                logger.debug(f"Ошибка проверки состояния страницы: {e}")
            
            # Если ничего определенного не найдено - неопределенность
            logger.warning("⚠️ Результат бронирования неясен")
            return {
                "success": False,
                "retry": True,
                "message": "⚠️ Результат бронирования неясен, возможна повторная попытка"
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки результата бронирования: {e}")
            return {
                "success": False,
                "retry": True,
                "message": f"❌ Ошибка проверки результата: {e}"
            }
    
    async def _get_booking_details(self, supply_id: str) -> Dict[str, Any]:
        """
        Получает детали бронирования: дату, склад, коэффициент.
        
        Args:
            supply_id: ID поставки
            
        Returns:
            Словарь с деталями бронирования
        """
        try:
            logger.info(f"📋 Получаю детали бронирования для поставки {supply_id}")
            
            # Дата, которую мы забронировали
            from datetime import datetime, timedelta
            # Если была передана кастомная дата, пытаемся ее получить из результата
            # По умолчанию используем дату через 3 дня
            target_date = datetime.now() + timedelta(days=3)
            booking_date = target_date.strftime('%d.%m.%Y')
            
            # Получаем API ключи пользователя для запроса к WB API
            from .database_service import DatabaseService
            db_service = DatabaseService()
            
            try:
                api_keys = await db_service.get_decrypted_api_keys(self.user_id)
                logger.info(f"🔑 API ключи для пользователя {self.user_id}: найдено {len(api_keys) if api_keys else 0}")
                
                if not api_keys:
                    logger.warning(f"⚠️ У пользователя {self.user_id} нет API ключей для получения деталей поставки")
                    return {
                        "booking_date": booking_date,
                        "warehouse_name": "Неизвестен (нет API ключа)",
                        "coefficient": "Неизвестен (нет API ключа)"
                    }
                
                # Используем первый доступный API ключ
                api_key = api_keys[0]
                
                # Получаем детали поставки через API
                from .wb_supplies_api import WBSuppliesAPIClient
                
                async with WBSuppliesAPIClient(api_key) as wb_api:
                    # ПРАВИЛЬНЫЙ СПОСОБ: Используем официальный API WB для получения деталей поставки
                    supply_details = None
                    
                    try:
                        # Сначала пробуем как ID поставки
                        logger.info(f"🔍 Пробую получить детали как ID поставки: {supply_id}")
                        supply_details = await wb_api.get_supply_details(supply_id, is_preorder_id=False)
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось получить как ID поставки: {e}")
                        
                        try:
                            # Если не получилось, пробуем как ID заказа (preorderID)
                            logger.info(f"🔍 Пробую получить детали как ID заказа: {supply_id}")
                            supply_details = await wb_api.get_supply_details(supply_id, is_preorder_id=True)
                        except Exception as e2:
                            logger.warning(f"⚠️ Не удалось получить как ID заказа: {e2}")
                            supply_details = None
                    
                    # Извлекаем склад из детальной информации
                    warehouse_name = "Неизвестен"
                    warehouse_id = None
                    
                    if supply_details:
                        logger.info(f"📋 Получены детали поставки: {supply_details}")
                        
                        # Согласно документации API, поля для склада:
                        warehouse_id = supply_details.get("warehouseID")
                        warehouse_name = supply_details.get("warehouseName", "Неизвестен")
                        
                        # Если основной склад не указан, проверяем actualWarehouse
                        if not warehouse_id:
                            warehouse_id = supply_details.get("actualWarehouseID")
                            warehouse_name = supply_details.get("actualWarehouseName", warehouse_name)
                        
                        logger.info(f"🏬 Извлечен склад: ID={warehouse_id}, Название={warehouse_name}")
                    else:
                        logger.warning(f"⚠️ Не удалось получить детали поставки {supply_id} через API")
                    
                    # Получаем коэффициент для даты бронирования
                    coefficient = "Неизвестен"
                    
                    # Сначала проверяем есть ли коэффициент в деталях поставки
                    if supply_details:
                        paid_coeff = supply_details.get("paidAcceptanceCoefficient")
                        if paid_coeff is not None:
                            coefficient = paid_coeff
                            logger.info(f"📊 Коэффициент из деталей поставки: {coefficient}")
                    
                    # Если коэффициента нет в деталях, получаем через API приёмки
                    if coefficient == "Неизвестен":
                        try:
                            date_str = target_date.strftime('%Y-%m-%d')
                            logger.info(f"🔍 Ищу коэффициент приёмки для даты {date_str}")
                            
                            if warehouse_id:
                                # Получаем коэффициенты для конкретного склада
                                coefficients = await wb_api.get_acceptance_coefficients([warehouse_id])
                                logger.info(f"📊 Получено {len(coefficients)} коэффициентов для склада {warehouse_id}")
                                
                                # Ищем коэффициент для нашей даты
                                for coeff in coefficients:
                                    coeff_date = coeff.get("date")
                                    coeff_warehouse = coeff.get("warehouseID")
                                    coeff_value = coeff.get("coefficient")
                                    
                                    logger.info(f"📊 Проверяю коэф: дата={coeff_date}, склад={coeff_warehouse}, значение={coeff_value}")
                                    
                                    if coeff_date == date_str and coeff_warehouse == warehouse_id:
                                        coefficient = coeff_value
                                        logger.info(f"✅ Найден коэффициент приёмки: {coefficient}")
                                        break
                            else:
                                # Если нет ID склада, получаем коэффициенты для всех складов
                                coefficients = await wb_api.get_acceptance_coefficients()
                                logger.info(f"📊 Получено {len(coefficients)} коэффициентов для всех складов")
                                
                                # Ищем любой коэффициент для нашей даты
                                for coeff in coefficients:
                                    if coeff.get("date") == date_str:
                                        coefficient = coeff.get("coefficient", "Неизвестен")
                                        logger.info(f"✅ Найден коэффициент приёмки {coefficient}")
                                        break
                                        
                        except Exception as coeff_error:
                            logger.warning(f"⚠️ Не удалось получить коэффициент приёмки: {coeff_error}")
                            coefficient = "Ошибка получения"
            
            except Exception as api_error:
                logger.warning(f"⚠️ Ошибка получения деталей через API: {api_error}")
                # FALLBACK: Хотя бы дату покажем
                return {
                    "booking_date": booking_date,
                    "warehouse_name": "API недоступен", 
                    "coefficient": "API недоступен"
                }
            
            logger.info(f"✅ Детали бронирования: дата={booking_date}, склад={warehouse_name}, коэф={coefficient}")
            
            return {
                "booking_date": booking_date,
                "warehouse_name": warehouse_name,
                "coefficient": coefficient
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения деталей бронирования: {e}")
            return {
                "booking_date": "Ошибка",
                "warehouse_name": "Ошибка",
                "coefficient": "Ошибка"
            }
    
    async def _find_new_supply_id(self) -> str:
        """
        Ищет новый ID поставки в заголовке страницы после успешного бронирования.
        WB меняет ID поставки после брони с preorderID на supplyID.
        
        Returns:
            Новый ID поставки или None если не найден
        """
        try:
            logger.info("🔍 Ищу новый ID поставки в заголовке страницы...")
            
            # Ждем загрузки страницы после бронирования
            await asyncio.sleep(3)
            
            # Селекторы для поиска заголовка "Поставка №..."
            header_selectors = [
                # Точный селектор из скриншота
                'span.Text_JKIsQramuu.Text--title-l_SORyypWwPl.Text--black_hIzfx5PELf.Text--white-space-break-spaces_Ap2G-5homnx.Text--textDecoration-none_rKzIphagq0',
                
                # Более общие селекторы
                'span[class*="Text_"][class*="title"]:has-text("Поставка")',
                'span[class*="Text--title"]:has-text("Поставка")',
                'h1:has-text("Поставка")',
                'h2:has-text("Поставка")', 
                'h3:has-text("Поставка")',
                
                # Поиск по тексту
                'text=/Поставка №\\d+/',
                '*:has-text("Поставка №")',
                
                # CSS селекторы с содержанием
                'span:has-text("Поставка №")',
                'div:has-text("Поставка №")',
                
                # Поиск в заголовках страницы
                '[role="heading"]:has-text("Поставка")',
                '.page-title:has-text("Поставка")',
                '.header:has-text("Поставка")',
            ]
            
            new_supply_id = None
            
            for selector in header_selectors:
                try:
                    logger.info(f"🔍 Пробую селектор: {selector}")
                    
                    # Ищем элементы с этим селектором
                    elements = self.page.locator(selector)
                    count = await elements.count()
                    
                    logger.info(f"📊 Найдено элементов: {count}")
                    
                    if count > 0:
                        for i in range(count):
                            element = elements.nth(i)
                            
                            if await element.is_visible():
                                text = await element.text_content()
                                logger.info(f"📝 Текст элемента {i}: '{text}'")
                                
                                if text and "Поставка №" in text:
                                    # Извлекаем номер поставки
                                    import re
                                    match = re.search(r'Поставка №(\d+)', text)
                                    if match:
                                        new_supply_id = match.group(1)
                                        logger.info(f"✅ Найден новый ID поставки: {new_supply_id}")
                                        return new_supply_id
                except Exception as e:
                    logger.debug(f"Ошибка с селектором {selector}: {e}")
                    continue
            
            # Если не нашли через селекторы, пробуем через page.content()
            try:
                logger.info("🔍 Ищу в HTML коде страницы...")
                page_content = await self.page.content()
                
                import re
                matches = re.findall(r'Поставка №(\d+)', page_content)
                if matches:
                    new_supply_id = matches[0]  # Берем первое совпадение
                    logger.info(f"✅ Найден ID в HTML: {new_supply_id}")
                    return new_supply_id
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка поиска в HTML: {e}")
            
            logger.warning("⚠️ Новый ID поставки не найден в заголовке")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска нового ID поставки: {e}")
            return None
    
    def _parse_custom_date(self, custom_date: str) -> datetime:
        """
        Парсит кастомную дату из различных форматов.
        
        Args:
            custom_date: Дата в формате 'DD.MM.YYYY' или 'YYYY-MM-DD'
            
        Returns:
            datetime объект
        """
        try:
            # Пробуем разные форматы
            formats = ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(custom_date, fmt)
                    logger.info(f"📅 Успешно распарсили дату '{custom_date}' как {parsed_date}")
                    return parsed_date
                except ValueError:
                    continue
            
            # Если ничего не подошло, используем дату через 3 дня
            logger.warning(f"⚠️ Не удалось распарсить дату '{custom_date}', используем дату через 3 дня")
            return datetime.now() + timedelta(days=3)
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга даты '{custom_date}': {e}")
            return datetime.now() + timedelta(days=3)
    
    async def _find_max_coefficient_date(self, available_dates) -> datetime:
        """
        Ищет дату с максимальным коэффициентом среди доступных дат.
        
        Args:
            available_dates: Playwright locator с доступными датами
            
        Returns:
            datetime объект с датой максимального коэффициента или None
        """
        try:
            logger.info("📊 Ищу дату с максимальным коэффициентом...")
            
            max_coefficient = 0
            best_date = None
            count = await available_dates.count()
            
            for i in range(count):
                date_element = available_dates.nth(i)
                
                try:
                    # Получаем текст даты
                    date_text = await date_element.text_content()
                    if not date_text:
                        continue
                    
                    # Ищем коэффициент в тексте (может быть рядом с датой)
                    coefficient_text = await self._find_coefficient_for_date(date_element)
                    
                    if coefficient_text:
                        try:
                            coefficient = float(coefficient_text.replace(',', '.'))
                            logger.info(f"📊 Дата: {date_text}, коэффициент: {coefficient}")
                            
                            if coefficient > max_coefficient:
                                max_coefficient = coefficient
                                # Парсим дату
                                parsed_date = self._parse_date_text(date_text)
                                if parsed_date:
                                    best_date = parsed_date
                                    logger.info(f"🏆 Новый максимальный коэффициент: {coefficient} для даты {best_date}")
                        except (ValueError, TypeError):
                            logger.debug(f"Не удалось конвертировать коэффициент: {coefficient_text}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Ошибка обработки даты {i}: {e}")
                    continue
            
            if best_date:
                logger.info(f"🎯 Найдена лучшая дата: {best_date} с коэффициентом {max_coefficient}")
                return best_date
            else:
                logger.warning("⚠️ Не найдено дат с коэффициентами")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска даты с максимальным коэффициентом: {e}")
            return None
    
    async def _find_first_available_date_with_min_hours(self, available_dates, min_hours_ahead: int) -> datetime:
        """
        Ищет ПЕРВУЮ активную (доступную) дату которая НЕ БЛИЖЕ чем min_hours_ahead часов от текущего времени.
        
        Args:
            available_dates: Playwright locator с доступными датами
            min_hours_ahead: Минимальное количество часов вперед (обычно 72-80)
            
        Returns:
            datetime объект с первой подходящей датой или None
        """
        try:
            from datetime import datetime, timedelta
            
            min_date = datetime.now() + timedelta(hours=min_hours_ahead)
            logger.info(f"🔍 Ищу ПЕРВУЮ доступную дату не ближе {min_hours_ahead}ч (минимум: {min_date.strftime('%d.%m.%Y %H:%M')})")
            
            count = await available_dates.count()
            
            for i in range(count):
                date_element = available_dates.nth(i)
                
                try:
                    # Получаем текст даты
                    date_text = await date_element.text_content()
                    if not date_text:
                        continue
                    
                    # Парсим дату
                    parsed_date = self._parse_date_text(date_text)
                    if not parsed_date:
                        continue
                    
                    # Проверяем что дата не ближе чем min_hours_ahead
                    if parsed_date >= min_date:
                        logger.info(f"✅ Найдена подходящая дата: {parsed_date.strftime('%d.%m.%Y')} (>= {min_date.strftime('%d.%m.%Y %H:%M')})")
                        return parsed_date
                    else:
                        logger.debug(f"⏭️ Дата {parsed_date.strftime('%d.%m.%Y')} слишком близко, ищу дальше...")
                        
                except Exception as e:
                    logger.debug(f"Ошибка обработки даты {i}: {e}")
                    continue
            
            logger.warning(f"⚠️ Не найдено дат не ближе {min_hours_ahead}ч")
            return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска первой доступной даты: {e}")
            return None
    
    async def _find_max_coefficient_date_with_min_hours(self, available_dates, min_hours_ahead: int) -> datetime:
        """
        Ищет дату с максимальным коэффициентом которая НЕ БЛИЖЕ чем min_hours_ahead часов.
        
        Args:
            available_dates: Playwright locator с доступными датами
            min_hours_ahead: Минимальное количество часов вперед
            
        Returns:
            datetime объект с датой максимального коэффициента или None
        """
        try:
            from datetime import datetime, timedelta
            
            min_date = datetime.now() + timedelta(hours=min_hours_ahead)
            logger.info(f"📊 Ищу дату с максимальным коэффициентом (не ближе {min_hours_ahead}ч)...")
            
            max_coefficient = 0
            best_date = None
            count = await available_dates.count()
            
            for i in range(count):
                date_element = available_dates.nth(i)
                
                try:
                    # Получаем текст даты
                    date_text = await date_element.text_content()
                    if not date_text:
                        continue
                    
                    # Парсим дату
                    parsed_date = self._parse_date_text(date_text)
                    if not parsed_date:
                        continue
                    
                    # Проверяем что дата не ближе чем min_hours_ahead
                    if parsed_date < min_date:
                        logger.debug(f"⏭️ Дата {parsed_date.strftime('%d.%m.%Y')} слишком близко, пропускаю")
                        continue
                    
                    # Ищем коэффициент в тексте (может быть рядом с датой)
                    coefficient_text = await self._find_coefficient_for_date(date_element)
                    
                    if coefficient_text:
                        try:
                            coefficient = float(coefficient_text.replace(',', '.'))
                            logger.info(f"📊 Дата: {date_text}, коэффициент: {coefficient}")
                            
                            if coefficient > max_coefficient:
                                max_coefficient = coefficient
                                best_date = parsed_date
                                logger.info(f"🏆 Новый максимум: коэффициент {coefficient} для даты {best_date}")
                        except (ValueError, TypeError):
                            logger.debug(f"Не удалось конвертировать коэффициент: {coefficient_text}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Ошибка обработки даты {i}: {e}")
                    continue
            
            if best_date:
                logger.info(f"🎯 Найдена лучшая дата: {best_date} с коэффициентом {max_coefficient}")
                return best_date
            else:
                logger.warning("⚠️ Не найдено дат с коэффициентами")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска даты с максимальным коэффициентом: {e}")
            return None
    
    async def _find_coefficient_for_date(self, date_element) -> str:
        """
        Ищет коэффициент для конкретной даты.
        
        Args:
            date_element: Playwright element с датой
            
        Returns:
            Строка с коэффициентом или None
        """
        try:
            # Ищем коэффициент приёмки в различных местах относительно элемента даты
            selectors = [
                # Коэффициент приёмки может быть в том же элементе
                '.coefficient',
                '[data-testid*="coefficient"]',
                '.coeff',
                '*[class*="acceptance"]',      # Приёмка
                '*[class*="logistic"]',        # Логистика  
                '*[class*="price"]',           # Цена
                
                # Или в соседних элементах
                '+ * .coefficient',
                '+ * [data-testid*="coefficient"]',
                '+ * *[class*="acceptance"]',
                '+ * *[class*="logistic"]',
                
                # Или в родительском элементе
                '../ .coefficient',
                '../ [data-testid*="coefficient"]',
                '../ *[class*="acceptance"]',
                '../ *[class*="logistic"]',
                
                # Или в дочерних элементах
                './/*[class*="acceptance"]',
                './/*[class*="logistic"]',
                './/*[contains(text(), "×")]',    # Поиск по символу умножения
                './/*[contains(text(), "₽")]',    # Поиск по рублям
            ]
            
            # Сначала наводим мышку на элемент даты для активации hover-эффектов
            try:
                await date_element.hover(timeout=2000, force=True)
                await asyncio.sleep(0.3)  # Даём время на появление hover-элементов
            except Exception as hover_error:
                logger.warning(f"⚠️ Ошибка наведения на дату: {hover_error}")
                # Продолжаем без наведения
            
            for selector in selectors:
                try:
                    coeff_element = date_element.locator(selector).first
                    if await coeff_element.is_visible():
                        coeff_text = await coeff_element.text_content()
                        logger.debug(f"🔍 Найден элемент с текстом: '{coeff_text}' через селектор: {selector}")
                        
                        if coeff_text and any(char.isdigit() for char in coeff_text):
                            # Проверяем паттерны приёмки
                            import re
                            patterns = [
                                r'×(\d+(?:[.,]\d+)?)',                    # ×2, ×1.5
                                r'приём[а-я]*[:\s]*(\d+(?:[.,]\d+)?)',   # приёмка: 2
                                r'(\d+(?:[.,]\d+)?)\s*≈\s*∼\s*\d+[.,]?\d*\s*₽',  # 2 ≈ ∼ 3,98 ₽
                                r'(\d+(?:[.,]\d+)?)\s*∼\s*\d+[.,]?\d*\s*₽',      # 2 ∼ 3,98 ₽
                                r'(\d+(?:[.,]\d+)?)%',                   # 200%
                                r'(\d+(?:[.,]\d+)?)',                    # Любое число
                            ]
                            
                            for pattern in patterns:
                                match = re.search(pattern, coeff_text, re.IGNORECASE)
                                if match:
                                    coefficient_value = match.group(1)
                                    logger.info(f"🎯 Найден коэффициент приёмки: {coefficient_value} в тексте: '{coeff_text}'")
                                    return coefficient_value
                except Exception as e:
                    logger.debug(f"Ошибка поиска через селектор {selector}: {e}")
                    continue
            
            # Ищем в тексте самого элемента даты
            element_text = await date_element.text_content()
            logger.debug(f"🔍 Текст элемента даты: '{element_text}'")
            
            # Также ищем в родительском элементе (может содержать информацию о приёмке)
            parent_element = date_element.locator('..')
            parent_text = ""
            try:
                parent_text = await parent_element.text_content()
                logger.debug(f"🔍 Текст родительского элемента: '{parent_text}'")
            except:
                pass
            
            # Объединяем тексты для поиска
            combined_text = f"{element_text} {parent_text}"
            
            if combined_text:
                import re
                # Ищем паттерны ПРИЁМКИ, ИСКЛЮЧАЯ логистику и хранение
                patterns = [
                    # ПРИОРИТЕТ: ищем коэффициенты рядом с acceptance/freeAcceptance
                    r'common-translates\.acceptance.*?(\d+(?:[.,]\d+)?)',  # common-translates.acceptance + число
                    r'freeAcceptance.*?(\d+(?:[.,]\d+)?)',                 # freeAcceptance + число  
                    r'choose-date\.freeAcceptance.*?(\d+(?:[.,]\d+)?)',    # choose-date.freeAcceptance + число
                    
                    # Классические паттерны приёмки
                    r'×(\d+(?:[.,]\d+)?)',                    # ×2, ×1.5
                    r'коэф[:\s]*(\d+(?:[.,]\d+)?)',          # коэф: 1.5
                    r'приём[а-я]*[:\s]*(\d+(?:[.,]\d+)?)',   # приёмка: 2
                    r'(\d+(?:[.,]\d+)?)\s*≈\s*∼\s*\d+[.,]?\d*\s*₽',  # 2 ≈ ∼ 3,98 ₽
                    r'(\d+(?:[.,]\d+)?)\s*∼\s*\d+[.,]?\d*\s*₽',      # 2 ∼ 3,98 ₽
                    r'\((\d+(?:[.,]\d+)?)\)',                # (2)
                    
                    # ИСКЛЮЧАЕМ logisticDescription и storageDescription!!!
                    # Ищем % только если НЕТ logistic/storage рядом
                ]
                
                # Сначала проверяем БЕСПЛАТНУЮ приёмку
                if 'freeAcceptance' in combined_text or 'common-translates.acceptance' in combined_text:
                    # Если есть маркеры бесплатной приёмки, коэффициент = 0
                    if 'choose-date.freeAcceptance' in combined_text:
                        logger.info(f"🎯 Найдена БЕСПЛАТНАЯ приёмка (choose-date.freeAcceptance)! Коэффициент = 0")
                        return "0"
                    elif 'common-translates.acceptance' in combined_text and 'logisticDescription' not in combined_text:
                        logger.info(f"🎯 Найдена БЕСПЛАТНАЯ приёмка (common-translates.acceptance)! Коэффициент = 0")
                        return "0"
                
                # КРИТИЧНО: исключаем любые коэффициенты из logistic и storage
                if 'logisticDescription' in combined_text or 'storageDescription' in combined_text:
                    logger.warning(f"⚠️ Найдены маркеры логистики/хранения - пропускаем: {combined_text[:100]}...")
                    return None
                
                for pattern in patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        coefficient_value = match.group(1)
                        logger.info(f"🎯 Найден коэффициент приёмки: {coefficient_value} из: '{combined_text}'")
                        return coefficient_value
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка поиска коэффициента: {e}")
            return None
    
    def _parse_date_text(self, date_text: str) -> datetime:
        """
        Парсит текст даты в datetime объект.
        
        Args:
            date_text: Текст с датой
            
        Returns:
            datetime объект или None
        """
        try:
            # Возможные форматы дат в интерфейсе WB
            patterns = [
                r'(\d{1,2})\s+(\w+)',  # "18 сентября"
                r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # "18.09.2024"
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # "18/09/2024"
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # "18-09-2024"
            ]
            
            current_year = datetime.now().year
            
            for pattern in patterns:
                match = re.search(pattern, date_text)
                if match:
                    if len(match.groups()) == 2:  # день и месяц словами
                        day = int(match.group(1))
                        month_name = match.group(2).lower()
                        
                        # Словарь месяцев на русском
                        months = {
                            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
                        }
                        
                        for month_text, month_num in months.items():
                            if month_text in month_name:
                                return datetime(current_year, month_num, day)
                    
                    elif len(match.groups()) == 3:  # день.месяц.год
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                        return datetime(year, month, day)
            
            logger.warning(f"⚠️ Не удалось распарсить дату: {date_text}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга текста даты '{date_text}': {e}")
            return None
    
    async def _find_coefficient_for_specific_date(self, target_date: datetime, available_dates) -> float:
        """
        Ищет коэффициент для конкретной выбранной даты.
        
        Args:
            target_date: Целевая дата для поиска коэффициента
            available_dates: Playwright locator с доступными датами
            
        Returns:
            float коэффициент или None если не найден
        """
        try:
            logger.info(f"📊 Ищу коэффициент для конкретной даты: {target_date.strftime('%d.%m.%Y')}")
            
            count = await available_dates.count()
            
            for i in range(count):
                date_element = available_dates.nth(i)
                
                try:
                    # Получаем текст даты
                    date_text = await date_element.text_content()
                    if not date_text:
                        continue
                    
                    # Парсим дату из текста
                    parsed_date = self._parse_date_text(date_text)
                    if not parsed_date:
                        continue
                    
                    # Проверяем соответствие даты
                    if (parsed_date.day == target_date.day and 
                        parsed_date.month == target_date.month and 
                        parsed_date.year == target_date.year):
                        
                        logger.info(f"✅ Найдена нужная дата: {date_text}")
                        
                        # Ищем коэффициент в этой дате
                        coefficient_text = await self._find_coefficient_for_date(date_element)
                        
                        if coefficient_text:
                            try:
                                coefficient = float(coefficient_text.replace(',', '.'))
                                logger.info(f"🎯 Коэффициент для даты {target_date.strftime('%d.%m.%Y')}: {coefficient}")
                                return coefficient
                            except (ValueError, TypeError):
                                logger.warning(f"⚠️ Не удалось распарсить коэффициент: {coefficient_text}")
                                continue
                        else:
                            logger.warning(f"⚠️ Коэффициент не найден для даты {target_date.strftime('%d.%m.%Y')}")
                            return None
                            
                except Exception as e:
                    logger.debug(f"Ошибка обработки даты {i}: {e}")
                    continue
            
            logger.warning(f"⚠️ Дата {target_date.strftime('%d.%m.%Y')} не найдена в календаре")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска коэффициента для даты {target_date.strftime('%d.%m.%Y')}: {e}")
            return None
    
    async def _find_coefficient_date(self, target_coefficient: float, available_dates) -> datetime:
        """
        Ищет дату с коэффициентом меньше или равным указанному.
        
        Args:
            target_coefficient: Максимальный допустимый коэффициент
            available_dates: Playwright locator с доступными датами
            
        Returns:
            datetime объект с подходящим коэффициентом или None
        """
        try:
            logger.info(f"📊 Ищу дату с коэффициентом <= {target_coefficient}...")
            
            count = await available_dates.count()
            best_date = None
            best_coefficient = float('inf')  # Начинаем с бесконечности
            
            for i in range(count):
                date_element = available_dates.nth(i)
                
                try:
                    # Получаем текст даты
                    date_text = await date_element.text_content()
                    if not date_text:
                        continue
                    
                    # Ищем коэффициент в тексте даты
                    coefficient_text = await self._find_coefficient_for_date(date_element)
                    
                    if coefficient_text:
                        try:
                            coefficient = float(coefficient_text.replace(',', '.'))
                            
                            # Проверяем что коэффициент <= целевого
                            if coefficient <= target_coefficient:
                                parsed_date = self._parse_date_text(date_text)
                                if parsed_date:
                                    # Выбираем дату с наименьшим подходящим коэффициентом
                                    if coefficient < best_coefficient:
                                        best_coefficient = coefficient
                                        best_date = parsed_date
                                        logger.info(f"✅ Новая лучшая дата с коэффициентом {coefficient}: {parsed_date}")
                            else:
                                logger.debug(f"⚠️ Коэффициент {coefficient} больше целевого {target_coefficient}")
                            
                        except (ValueError, TypeError):
                            continue
                            
                except Exception as e:
                    logger.debug(f"Ошибка обработки даты {i}: {e}")
                    continue
            
            # Особая обработка для бесплатного коэффициента (0)
            if target_coefficient >= 0 and best_date is None:
                logger.info("🔍 Ищу бесплатные слоты...")
                page_content = await self.page.content()
                if "бесплатно" in page_content.lower() or "free" in page_content.lower():
                    # Возвращаем первую доступную дату для бесплатного слота
                    first_element = available_dates.first
                    if await first_element.count() > 0:
                        first_date_text = await first_element.text_content()
                        if first_date_text:
                            parsed_date = self._parse_date_text(first_date_text)
                            if parsed_date:
                                logger.info(f"✅ Найден бесплатный слот на дату: {parsed_date}")
                                return parsed_date
            
            if best_date:
                logger.info(f"✅ Выбрана лучшая дата с коэффициентом {best_coefficient}: {best_date}")
                return best_date
            else:
                logger.warning(f"⚠️ Дата с коэффициентом <= {target_coefficient} не найдена")
                return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска даты с коэффициентом <= {target_coefficient}: {e}")
            return None
    
    async def _find_suitable_date_from_list(self, selected_dates: list, target_coefficient: float, available_dates) -> datetime:
        """
        Ищет подходящую дату из списка выбранных пользователем дат.
        Проверяет коэффициент только для выбранных дат и возвращает дату где коэффициент <= целевого.
        
        Args:
            selected_dates: Список дат в формате 'DD.MM.YYYY' выбранных пользователем
            target_coefficient: Максимальный допустимый коэффициент
            available_dates: Playwright locator с доступными датами
            
        Returns:
            datetime объект подходящей даты или None
        """
        try:
            logger.info(f"📊 Ищу подходящую дату из списка {selected_dates} с коэффициентом <= {target_coefficient}...")
            
            best_date = None
            best_coefficient = float('inf')
            
            # Проверяем каждую выбранную дату
            for date_str in selected_dates:
                try:
                    # Парсим дату (используем существующий метод)
                    target_date = self._parse_custom_date(date_str)
                    if not target_date:
                        logger.warning(f"⚠️ Не удалось распарсить дату: {date_str}")
                        continue
                    
                    # Ищем коэффициент для этой конкретной даты
                    actual_coefficient = await self._find_coefficient_for_specific_date(target_date, available_dates)
                    
                    if actual_coefficient is not None:
                        logger.info(f"📊 Дата {date_str}: коэффициент {actual_coefficient}")
                        
                        # Проверяем что коэффициент <= целевого
                        if actual_coefficient <= target_coefficient:
                            # Выбираем дату с наименьшим подходящим коэффициентом
                            if actual_coefficient < best_coefficient:
                                best_coefficient = actual_coefficient
                                best_date = target_date
                                logger.info(f"✅ Новая лучшая дата: {date_str} с коэффициентом {actual_coefficient}")
                        else:
                            logger.info(f"❌ Дата {date_str}: коэффициент {actual_coefficient} > {target_coefficient}")
                    else:
                        logger.warning(f"⚠️ Не удалось найти коэффициент для даты {date_str}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки даты {date_str}: {e}")
                    continue
            
            if best_date:
                logger.info(f"🎯 Выбрана лучшая дата из списка: {best_date.strftime('%d.%m.%Y')} с коэффициентом {best_coefficient}")
                return best_date
            else:
                logger.warning(f"⚠️ Среди выбранных дат нет подходящих с коэффициентом <= {target_coefficient}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска подходящей даты из списка: {e}")
            return None
    
    async def _human_type(self, selector: str, text: str, delay_range: tuple = (50, 150)):
        """Человеческий ввод текста с вариативными задержками."""
        element = await self.page.wait_for_selector(selector, timeout=10000)
        await element.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Очищаем поле
        await element.fill("")
        await asyncio.sleep(random.uniform(0.05, 0.1))
        
        # Вводим по символу с человеческими задержками
        for char in text:
            await element.type(char, delay=random.randint(*delay_range))
            if random.random() < 0.1:  # 10% шанс на дополнительную паузу
                await asyncio.sleep(random.uniform(0.1, 0.3))
    
    async def _human_click(self, selector: str, delay_before: tuple = (0.1, 0.3)):
        """Человеческий клик с задержкой и движением мыши."""
        await asyncio.sleep(random.uniform(*delay_before))
        
        element = await self.page.wait_for_selector(selector, timeout=1000)
        
        # Наводим мышь на элемент
        try:
            await element.hover(timeout=2000, force=True)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception as hover_error:
            logger.warning(f"⚠️ Ошибка наведения: {hover_error}")
            # Продолжаем без наведения
        
        # Кликаем
        await element.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    async def check_if_logged_in(self) -> bool:
        """Проверяет, авторизован ли пользователь в WB и обновляет данные в БД."""
        try:
            logger.info("🔍 Проверяю авторизацию в WB...")
            
            # Сначала проверяем, что браузер и страница работают
            if not self.page or self.page.is_closed():
                logger.error("❌ Браузер или страница закрыты")
                return False
            
            # ПРИОРИТЕТ 1: Проверяем валидную сессию в БД (быстрая проверка)
            if self.user_id:
                is_valid_session = await db_service.is_browser_session_valid(self.user_id)
                if is_valid_session:
                    logger.info(f"✅ Найдена валидная сессия в БД для пользователя {self.user_id}")
                    # Дополнительно пробуем проверить через браузер (неблокирующе)
                    try:
                        await self._quick_browser_check()
                    except Exception as e:
                        logger.warning(f"⚠️ Быстрая проверка браузера не удалась: {e}")
                    return True
            
            # ПРИОРИТЕТ 2: Если сессии нет в БД, пробуем проверить через браузер
            try:
                # Переходим на страницу поставок для проверки авторизации
                supplies_url = "https://seller.wildberries.ru/supplies-management/all-supplies"
                response = await self.page.goto(supplies_url, wait_until="domcontentloaded", timeout=10000)  # Уменьшили таймаут
                
                if response and response.status == 200:
                    current_url = self.page.url
                    logger.info(f"📍 Текущий URL: {current_url}")
                    
                    # Проверяем признаки авторизации
                    is_logged_in = any([
                        'seller.wildberries.ru' in current_url and 'login' not in current_url,
                        'supplies-management' in current_url,
                        'lk-seller.wildberries.ru' in current_url
                    ])
                    
                    # Обновляем данные в БД если указан user_id
                    if self.user_id:
                        if is_logged_in:
                            await db_service.update_browser_session_login_success(self.user_id, "session_check")
                            logger.info(f"💾 Обновлена БД: пользователь {self.user_id} авторизован")
                        else:
                            # Не считаем это неудачной попыткой входа, просто обновляем время проверки
                            session_data = await db_service.get_browser_session_data(self.user_id)
                            if session_data:
                                logger.info(f"💾 Пользователь {self.user_id} не авторизован, но сессия существует")
                    
                    if is_logged_in:
                        logger.info("✅ Пользователь уже авторизован!")
                        return True
                    else:
                        logger.info("❌ Пользователь не авторизован")
                        return False
                else:
                    logger.error("❌ Не удалось загрузить страницу для проверки авторизации")
                    return False
                    
            except Exception as browser_error:
                logger.warning(f"⚠️ Ошибка при проверке через браузер: {browser_error}")
                # Если браузер не может подключиться, но есть валидная сессия в БД - считаем авторизованным
                if self.user_id:
                    is_valid_session = await db_service.is_browser_session_valid(self.user_id)
                    if is_valid_session:
                        logger.info(f"✅ Используем валидную сессию из БД для пользователя {self.user_id}")
                        return True
                return False
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки авторизации: {e}")
            # При ошибке проверяем БД как последний шанс
            if self.user_id:
                try:
                    is_valid_session = await db_service.is_browser_session_valid(self.user_id)
                    if is_valid_session:
                        logger.info(f"✅ Используем валидную сессию из БД для пользователя {self.user_id}")
                        return True
                except:
                    pass
            return False
    
    async def _quick_browser_check(self) -> None:
        """Быстрая проверка браузера без блокировки основного процесса."""
        try:
            # Пробуем быстро проверить текущий URL
            current_url = self.page.url
            if any([
                'seller.wildberries.ru' in current_url and 'login' not in current_url,
                'supplies-management' in current_url,
                'lk-seller.wildberries.ru' in current_url
            ]):
                logger.info("✅ Быстрая проверка: пользователь авторизован в браузере")
            else:
                logger.info("ℹ️ Быстрая проверка: статус авторизации неопределен")
        except Exception as e:
            logger.debug(f"Быстрая проверка браузера не удалась: {e}")

    async def login_step1_phone(self, phone: str) -> bool:
        """Шаг 1: Ввод номера телефона с максимальной человечностью."""
        
        # Инициализируем переменные для всех номеров
        kg_selected = False
        country_selector = None
        
        try:
            logger.info("🔐 Начинаю процесс входа в WB...")
            
            # Пробуем разные страницы входа (актуальные URL WB 2024)
            login_urls = [
                "https://seller-auth.wildberries.ru/ru/?redirect_url=https%3A%2F%2Fseller.wildberries.ru%2F&fromSellerLanding",  # АКТУАЛЬНАЯ ССЫЛКА
                "https://seller.wildberries.ru/",
                "https://seller-auth.wildberries.ru/",
                "https://lk-seller.wildberries.ru/"
            ]
            
            page_loaded = False
            for url in login_urls:
                try:
                    logger.info(f"🔗 Пробую загрузить: {url}")
                    
                    # Переходим на страницу с расширенной диагностикой
                    response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    # Подробная диагностика ответа
                    if response:
                        logger.info(f"📊 Статус ответа: {response.status}")
                        logger.info(f"📊 URL после редиректа: {response.url}")
                        logger.info(f"📊 Заголовки: {response.headers}")
                        
                        if response.status == 200:
                            logger.info(f"✅ Страница загружена успешно: {url}")
                            page_loaded = True
                            break
                        else:
                            logger.warning(f"⚠️ Неожиданный статус {response.status} для {url}")
                    else:
                        logger.error(f"❌ Нет ответа от {url}")
                        
                    # Проверяем текущий URL после попытки загрузки
                    current_url = self.page.url
                    logger.info(f"🔍 Текущий URL после попытки: {current_url}")
                    
                    if "chrome-error" in current_url:
                        logger.error(f"🚫 Ошибка сети для {url}: {current_url}")
                        continue
                    elif current_url != url:
                        logger.info(f"🔄 Редирект: {url} → {current_url}")
                        page_loaded = True
                        break
                    else:
                        page_loaded = True
                        break
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка загрузки {url}: {e}")
                    continue
            
            if not page_loaded:
                logger.error("❌ Не удалось загрузить ни одну страницу входа")
                return False
            
            # Ждем полной загрузки страницы и рендера React/Vue компонентов
            await asyncio.sleep(random.uniform(5, 8))  # Увеличиваю время ожидания
            
            # ДИАГНОСТИКА: Проверяем HTML содержимое страницы
            page_content = await self.page.content()
            logger.info(f"🔍 HTML содержимое (первые 500 символов): {page_content[:500]}")
            logger.info(f"🔍 Размер HTML: {len(page_content)} символов")
            
            # Проверяем есть ли JavaScript ошибки
            try:
                js_errors = await self.page.evaluate("() => window.console.error.toString()")
                logger.info(f"🔍 JS ошибки: {js_errors}")
            except:
                pass
            
            # ДИАГНОСТИКА: Проверяем на капчу, блокировку, редирект
            current_url = self.page.url
            logger.info(f"🔍 Текущий URL после загрузки: {current_url}")
            
            # Проверяем есть ли слова "блокировка", "капча", "доступ запрещен"
            page_text = await self.page.inner_text('body')
            suspicious_words = ['блокировка', 'капча', 'captcha', 'доступ запрещен', 'access denied', 'blocked', 'bot']
            for word in suspicious_words:
                if word.lower() in page_text.lower():
                    logger.error(f"🚫 Обнаружена блокировка/капча: найдено слово '{word}'")
                    logger.info(f"🔍 Текст страницы (первые 300 символов): {page_text[:300]}")
                    
            # Проверяем все элементы на странице
            all_elements = await self.page.query_selector_all('*')
            logger.info(f"🔍 Всего элементов на странице: {len(all_elements)}")
            
            # Ищем любые формы
            forms = await self.page.query_selector_all('form')
            logger.info(f"🔍 Найдено форм: {len(forms)}")
            
            # Ищем кнопки
            buttons = await self.page.query_selector_all('button')
            logger.info(f"🔍 Найдено кнопок: {len(buttons)}")
            
            # Ищем ссылки
            links = await self.page.query_selector_all('a')
            logger.info(f"🔍 Найдено ссылок: {len(links)}")
            
            # Если нет никаких элементов ввода, пробуем обновить страницу
            all_inputs = await self.page.query_selector_all('input, textarea, [contenteditable="true"]')
            if len(all_inputs) == 0:
                logger.warning("🔄 НЕТ ПОЛЕЙ ВВОДА! Пробую обновить страницу...")
                await self.page.reload(wait_until="networkidle")
                await asyncio.sleep(5)
                
                # Повторная проверка после обновления
                all_inputs_after_reload = await self.page.query_selector_all('input, textarea, [contenteditable="true"]')
                logger.info(f"🔍 После обновления найдено полей ввода: {len(all_inputs_after_reload)}")
                
                if len(all_inputs_after_reload) == 0:
                    # Последняя попытка - попробовать другой URL
                    logger.warning("🔄 Пробую загрузить альтернативный URL...")
                    try:
                        await self.page.goto("https://lk.wildberries.ru/", wait_until="networkidle")
                        await asyncio.sleep(5)
                        final_inputs = await self.page.query_selector_all('input, textarea, [contenteditable="true"]')
                        logger.info(f"🔍 На альтернативном URL найдено полей: {len(final_inputs)}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка загрузки альтернативного URL: {e}")
            
            # Ждем появления любого input поля (для React/Vue приложений) - увеличиваю timeout
            try:
                await self.page.wait_for_selector('input', timeout=30000)  # 30 секунд
                logger.info("✅ Input поля появились после рендера")
            except:
                logger.warning("⚠️ Input поля не появились за 30 секунд, ищу в iframe и shadow DOM")
                
                # Проверяем iframe
                frames = self.page.frames
                for frame in frames:
                    try:
                        inputs = await frame.query_selector_all('input')
                        if inputs:
                            logger.info(f"✅ Найдены input в iframe: {len(inputs)}")
                            self.page = frame  # Переключаемся на iframe
                            break
                    except:
                        continue
                
                await asyncio.sleep(3)  # Дополнительное ожидание
            
            if self.debug_mode:
                await self.page.screenshot(path="wb_login_page.png")
                logger.info("📸 Скриншот страницы сохранен")
            
            # Проверяем не попали ли мы на главную страницу вместо страницы входа
            current_url = self.page.url
            page_title = await self.page.title()
            
            # Если заголовок содержит "Вход" - мы на правильной странице
            if "Вход" in page_title or "Авторизация" in page_title or "Логин" in page_title:
                logger.info("✅ Находимся на странице входа")
            elif "about-portal" in current_url or current_url.endswith("/ru/ru") or ("/seller" in current_url and "auth" not in current_url):
                logger.info("🔄 Попали на главную страницу, ищу кнопку входа...")
                
                # Ищем кнопку "Войти" (обновленные селекторы)
                login_buttons = [
                    # Ссылки на страницы входа
                    'a[href*="signin"]',
                    'a[href*="login"]',
                    'a[href*="auth"]',
                    'a[href*="seller-auth"]',
                    'a[href*="lk-seller"]',
                    
                    # Кнопки и ссылки с текстом
                    'button:has-text("Войти")',
                    'a:has-text("Войти")',
                    'button:has-text("Вход")',
                    'a:has-text("Вход")',
                    'button:has-text("Авторизация")',
                    'a:has-text("Авторизация")',
                    'button:has-text("Личный кабинет")',
                    'a:has-text("Личный кабинет")',
                    'button:has-text("Для продавцов")',
                    'a:has-text("Для продавцов")',
                    
                    # Data-атрибуты
                    '[data-testid*="login"]',
                    '[data-testid*="auth"]',
                    '[data-testid*="signin"]',
                    '[data-cy*="login"]',
                    '[data-cy*="auth"]',
                    
                    # Классы
                    '.login-button',
                    '.auth-button',
                    '.signin-button',
                    '.btn-login',
                    '.btn-auth',
                    
                    # ID
                    '#login-btn',
                    '#auth-btn',
                    '#signin-btn',
                    '#login',
                    '#auth'
                ]
                
                login_clicked = False
                for selector in login_buttons:
                    try:
                        button = await self.page.query_selector(selector)
                        if button and await button.is_visible():
                            logger.info(f"✅ Найдена кнопка входа: {selector}")
                            await button.click()
                            await self.page.wait_for_load_state('networkidle', timeout=10000)
                            login_clicked = True
                            break
                    except:
                        continue
                
                if not login_clicked:
                    logger.warning("⚠️ Кнопка входа не найдена, пробую прямой переход")
                    try:
                        await self.page.goto("https://seller-auth.wildberries.ru/", wait_until="networkidle")
                    except:
                        try:
                            await self.page.goto("https://lk-seller.wildberries.ru/", wait_until="networkidle")
                        except:
                            logger.error("❌ Не удалось загрузить ни одну страницу входа")
            
            # Умный поиск поля телефона (обновленные селекторы для WB 2024)
            phone_selectors = [
                # Актуальные селекторы WB
                'input[data-testid="phone-input"]',
                'input[data-testid="login-input"]',
                'input[name="phone"]',
                'input[name="phoneNumber"]',
                'input[name="login"]',
                'input[name="username"]',
                'input[type="tel"]',
                
                # По placeholder (русский и английский)
                'input[placeholder*="телефон" i]',
                'input[placeholder*="номер" i]',
                'input[placeholder*="phone" i]',
                'input[placeholder*="Телефон" i]',
                'input[placeholder*="Номер" i]',
                'input[placeholder*="+7" i]',
                
                # По ID
                '#phone',
                '#phoneNumber',
                '#login',
                '#username',
                '#phone-input',
                '#login-input',
                
                # По классам
                '.phone-input input',
                '.login-input input',
                '.auth-input input',
                '.form-control[type="tel"]',
                'input[class*="phone" i]',
                'input[class*="login" i]',
                'input[class*="auth" i]',
                
                # Современные React/Vue селекторы
                '[data-cy="phone"]',
                '[data-cy="login"]',
                '[role="textbox"][type="tel"]',
                'input[autocomplete="tel"]',
                'input[autocomplete="username"]',
                
                # Fallback - любой видимый input
                'form input[type="text"]:first-of-type',
                'form input[type="tel"]:first-of-type',
                'form input:not([type="hidden"]):first-of-type',
                'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):first-of-type'
            ]
            
            phone_input = None
            for selector in phone_selectors:
                try:
                    # Проверяем что элемент существует и видимый
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        phone_input = selector
                        logger.info(f"✅ Найдено поле телефона: {selector}")
                        break
                except:
                    continue
            
            if not phone_input:
                logger.error("❌ Не найдено поле для ввода телефона")
                
                # Показываем все input элементы для отладки + поиск в Shadow DOM
                inputs = await self.page.query_selector_all('input')
                logger.info(f"🔍 Найдено {len(inputs)} input элементов:")
                
                # Ищем в Shadow DOM
                if len(inputs) == 0:
                    logger.info("🔍 Ищу в Shadow DOM...")
                    shadow_inputs = await self.page.evaluate("""
                        () => {
                            const allElements = document.querySelectorAll('*');
                            let shadowInputs = [];
                            allElements.forEach(el => {
                                if (el.shadowRoot) {
                                    const inputs = el.shadowRoot.querySelectorAll('input');
                                    shadowInputs = shadowInputs.concat(Array.from(inputs));
                                }
                            });
                            return shadowInputs.map(inp => ({
                                type: inp.type,
                                name: inp.name,
                                id: inp.id,
                                placeholder: inp.placeholder,
                                className: inp.className
                            }));
                        }
                    """)
                    if shadow_inputs:
                        logger.info(f"✅ Найдено {len(shadow_inputs)} input в Shadow DOM: {shadow_inputs}")
                
                # Ищем все возможные поля ввода
                all_inputs = await self.page.query_selector_all('input, textarea, [contenteditable="true"], [role="textbox"]')
                logger.info(f"🔍 Всего полей ввода (включая textarea): {len(all_inputs)}")
                
                # Также ищем все элементы с текстом "телефон" или "phone"
                all_elements = await self.page.query_selector_all('*')
                phone_related = []
                for el in all_elements[:50]:  # Ограничиваем до 50 элементов
                    try:
                        text = await el.inner_text()
                        if text and ('телефон' in text.lower() or 'phone' in text.lower() or 'номер' in text.lower()):
                            tag = await el.evaluate('el => el.tagName')
                            phone_related.append(f"{tag}: {text[:50]}")
                    except:
                        pass
                
                if phone_related:
                    logger.info(f"📱 Элементы связанные с телефоном: {phone_related[:10]}")
                
                # Проверяем заголовок страницы
                title = await self.page.title()
                logger.info(f"📄 Заголовок страницы: {title}")
                
                # Проверяем URL
                url = self.page.url
                logger.info(f"🔗 Текущий URL: {url}")
                
                # ПРИНУДИТЕЛЬНЫЙ ПОИСК ЧЕРЕЗ JAVASCRIPT
                logger.info("🚀 ПРИНУДИТЕЛЬНЫЙ ПОИСК input полей через JavaScript...")
                js_inputs = await self.page.evaluate("""
                    () => {
                        // Ищем ВСЕ input элементы включая скрытые
                        const inputs = Array.from(document.querySelectorAll('input'));
                        const textareas = Array.from(document.querySelectorAll('textarea'));
                        const editables = Array.from(document.querySelectorAll('[contenteditable="true"]'));
                        const textboxes = Array.from(document.querySelectorAll('[role="textbox"]'));
                        
                        const allFields = [...inputs, ...textareas, ...editables, ...textboxes];
                        
                        return allFields.map((el, index) => ({
                            index: index,
                            tagName: el.tagName,
                            type: el.type || 'unknown',
                            name: el.name || '',
                            id: el.id || '',
                            className: el.className || '',
                            placeholder: el.placeholder || '',
                            value: el.value || '',
                            visible: el.offsetParent !== null,
                            display: window.getComputedStyle(el).display,
                            visibility: window.getComputedStyle(el).visibility,
                            outerHTML: el.outerHTML.substring(0, 200)
                        }));
                    }
                """)
                
                if js_inputs:
                    logger.info(f"🎯 JavaScript нашел {len(js_inputs)} полей ввода:")
                    for inp in js_inputs[:10]:  # Показываем первые 10
                        logger.info(f"  JS поле: {inp}")
                else:
                    logger.error("💀 JavaScript НЕ НАШЕЛ НИ ОДНОГО ПОЛЯ ВВОДА!")
                
                for i, inp in enumerate(inputs):
                    try:
                        attrs = await inp.evaluate("""el => ({
                            type: el.type,
                            name: el.name,
                            id: el.id,
                            className: el.className,
                            placeholder: el.placeholder,
                            visible: !el.hidden && el.offsetParent !== null
                        })""")
                        logger.info(f"  {i+1}. {attrs}")
                    except:
                        pass
                return False
            
            # ВАЖНО: Сначала выбираем правильный регион для киргизских номеров
            if phone.startswith('+996'):
                logger.info("🇰🇬 Обнаружен киргизский номер, ищу выбор региона...")
                
                # ДИАГНОСТИКА: Сначала посмотрим что есть на странице
                logger.info("🔍 ДИАГНОСТИКА: Анализирую всю страницу для поиска флажка...")
                try:
                    # Получаем весь текст страницы для анализа
                    page_text = await self.page.inner_text('body')
                    logger.info(f"🔍 Содержит ли страница '+7': {'+7' in page_text}")
                    logger.info(f"🔍 Содержит ли страница 'RU': {'RU' in page_text}")
                    logger.info(f"🔍 Содержит ли страница '🇷🇺': {'🇷🇺' in page_text}")
                    
                    # Ищем все элементы с текстом +7
                    plus7_elements = await self.page.query_selector_all('*')
                    plus7_count = 0
                    for el in plus7_elements[:50]:  # Первые 50 элементов
                        try:
                            text = await el.inner_text()
                            if text and '+7' in text:
                                plus7_count += 1
                                tag_name = await el.evaluate('el => el.tagName')
                                class_name = await el.evaluate('el => el.className || ""')
                                is_visible = await el.is_visible()
                                logger.info(f"🎯 Элемент с +7: {tag_name} class='{class_name}' visible={is_visible} text='{text[:50]}'")
                        except:
                            continue
                    logger.info(f"📊 Всего найдено элементов с +7: {plus7_count}")
                    
                    # Ищем все изображения (возможные флаги)
                    images = await self.page.query_selector_all('img')
                    logger.info(f"🖼️ Найдено изображений на странице: {len(images)}")
                    for i, img in enumerate(images[:10]):  # Первые 10 изображений
                        try:
                            src = await img.get_attribute('src')
                            alt = await img.get_attribute('alt')
                            is_visible = await img.is_visible()
                            logger.info(f"  {i+1}. IMG src='{src}' alt='{alt}' visible={is_visible}")
                        except:
                            continue
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка диагностики страницы: {e}")
                
                # Ищем селектор страны/региона (флажок РФ и +7)
                country_selectors = [
                    # ПРИОРИТЕТ 1: WB SVG флаги (найденные в исследовании)
                    'img[src*="country-flags/ru.svg"]',
                    'img[src*="/ru.svg"]',
                    '*:has(img[src*="country-flags/ru.svg"])',
                    'div:has(img[src*="/ru.svg"])',
                    'button:has(img[src*="/ru.svg"])',
                    
                    # ПРИОРИТЕТ 2: Ищем именно флаг РФ и +7
                    '*:has-text("+7")',
                    'div:has-text("+7")',
                    'button:has-text("+7")',
                    'span:has-text("+7")',
                    'text="+7"',
                    
                    # Российский флаг эмодзи и символы
                    '*:has-text("🇷🇺")',
                    'div:has-text("🇷🇺")',
                    'button:has-text("🇷🇺")',
                    '*:has-text("RU")',
                    
                    # Элементы с российским флагом (изображения)
                    'img[alt*="Russia"]',
                    'img[alt*="Russian"]',
                    'img[alt*="RU"]',
                    'img[src*="ru"]',
                    'img[src*="russia"]',
                    
                    # Флажок рядом с полем ввода
                    'div[class*="flag"]',
                    'button[class*="flag"]', 
                    'span[class*="flag"]',
                    '.flag-dropdown',
                    '.country-flag',
                    
                    # Селекторы рядом с input полем
                    'input[data-testid="phone-input"] ~ div',
                    'input[data-testid="phone-input"] + div',
                    
                    # Общие селекторы выпадающих списков
                    '[data-testid="country-selector"]',
                    '.country-select',
                    'select[name="country"]',
                    'div[class*="country"]',
                    'button[class*="country"]',
                    '.phone-country-selector',
                    '[role="combobox"]',
                    
                    # Поиск по соседним элементам с флагом
                    'div:has(img[alt*="flag"])',
                    'button:has(img[alt*="flag"])',
                    'div:has(.flag)',
                    'button:has(.flag)'
                ]
                
                country_selector = None
                for selector in country_selectors:
                    try:
                        logger.info(f"🔍 Пробую селектор: {selector}")
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            country_selector = element
                            logger.info(f"✅ Найден селектор страны: {selector}")
                            break
                        elif element:
                            logger.info(f"⚠️ Элемент найден но не видимый: {selector}")
                        else:
                            logger.info(f"❌ Элемент не найден: {selector}")
                    except Exception as e:
                        logger.debug(f"⚠️ Селектор {selector} не сработал: {e}")
                        continue
                
                # ДИАГНОСТИКА: Если не нашли флажок, ищем ВСЕ элементы рядом с полем ввода
                if not country_selector:
                    logger.warning("🔍 Флажок РФ/+7 не найден! Начинаю диагностику всех элементов...")
                    
                    # СПЕЦИАЛЬНЫЙ ПОИСК: Ищем ВСЕ элементы содержащие +7 или флаг РФ
                    try:
                        logger.info("🔍 Ищу ВСЕ элементы с +7 или флагом РФ...")
                        all_elements = await self.page.query_selector_all('*')
                        
                        for element in all_elements[:100]:  # Проверяем первые 100 элементов
                            try:
                                inner_text = await element.inner_text()
                                if inner_text and ('+7' in inner_text or '🇷🇺' in inner_text or 'RU' in inner_text):
                                    is_visible = await element.is_visible()
                                    if is_visible:
                                        tag_name = await element.evaluate('el => el.tagName')
                                        class_name = await element.evaluate('el => el.className || ""')
                                        logger.info(f"🎯 Найден элемент с +7/РФ: {tag_name} class='{class_name}' text='{inner_text[:30]}'")
                                        
                                        # Пробуем кликнуть по этому элементу
                                        try:
                                            await element.click()
                                            logger.info("✅ Кликнул по элементу с +7/РФ, ожидаю выпадающий список...")
                                            await asyncio.sleep(3)
                                            
                                            # Проверяем появился ли список стран
                                            dropdown_selectors = ['ul', 'div[role="listbox"]', '.dropdown', '[role="menu"]', 'li']
                                            dropdown_found = False
                                            for dropdown_sel in dropdown_selectors:
                                                dropdowns = await self.page.query_selector_all(dropdown_sel)
                                                for dropdown in dropdowns:
                                                    if await dropdown.is_visible():
                                                        dropdown_text = await dropdown.inner_text()
                                                        if dropdown_text and ('996' in dropdown_text or 'Кыргыз' in dropdown_text or 'Kyrgyz' in dropdown_text):
                                                            logger.info(f"✅ Найден выпадающий список с Кыргызстаном!")
                                                            dropdown_found = True
                                                            break
                                                if dropdown_found:
                                                    break
                                            
                                            if dropdown_found:
                                                # Ищем и кликаем по Кыргызстану
                                                kg_terms = ['996', 'Кыргыз', 'Kyrgyz', 'KG']
                                                for term in kg_terms:
                                                    try:
                                                        kg_elements = await self.page.query_selector_all(f'*:has-text("{term}")')
                                                        for kg_el in kg_elements:
                                                            if await kg_el.is_visible():
                                                                await kg_el.click()
                                                                logger.info(f"✅ УСПЕШНО выбран Кыргызстан по термину: {term}")
                                                                kg_selected = True
                                                                await asyncio.sleep(2)
                                                                break
                                                        if kg_selected:
                                                            break
                                                    except:
                                                        continue
                                                
                                                if kg_selected:
                                                    country_selector = element  # Помечаем что нашли селектор
                                                    break
                                        except Exception as click_error:
                                            logger.debug(f"⚠️ Ошибка клика по элементу: {click_error}")
                                            continue
                            except:
                                continue
                            
                            if kg_selected:
                                break
                    except Exception as e:
                        logger.error(f"❌ Ошибка специального поиска: {e}")
                    
                    # Ищем все элементы рядом с полем телефона
                    if not country_selector:
                        try:
                            # Получаем родительский контейнер поля ввода
                            phone_container = await self.page.query_selector('input[data-testid="phone-input"]')
                            if phone_container:
                                # Ищем соседние элементы
                                parent = await phone_container.query_selector('..')  # Родитель
                                if parent:
                                    siblings = await parent.query_selector_all('*')
                                    logger.info(f"📋 Найдено элементов в контейнере: {len(siblings)}")
                                    
                                    for i, sibling in enumerate(siblings[:10]):  # Первые 10
                                        try:
                                            tag_name = await sibling.evaluate('el => el.tagName')
                                            class_name = await sibling.evaluate('el => el.className')
                                            inner_text = await sibling.evaluate('el => el.innerText?.substring(0, 50)')
                                            is_clickable = await sibling.evaluate('el => el.onclick !== null || el.style.cursor === "pointer"')
                                            
                                            logger.info(f"  {i+1}. {tag_name} class='{class_name}' text='{inner_text}' clickable={is_clickable}")
                                            
                                            # Если элемент содержит флаг или код страны, пробуем его
                                            if (class_name and ('flag' in class_name.lower() or 'country' in class_name.lower())) or \
                                               (inner_text and ('+7' in inner_text or 'RU' in inner_text or '🇷🇺' in inner_text)):
                                                logger.info(f"🎯 ПОТЕНЦИАЛЬНЫЙ ФЛАЖОК найден: {tag_name}")
                                                country_selector = sibling
                                                break
                                                
                                        except Exception as e:
                                            logger.debug(f"Ошибка анализа элемента {i}: {e}")
                                            continue
                        except Exception as e:
                            logger.error(f"❌ Ошибка диагностики: {e}")
                    
                    # Дополнительный поиск по всей странице
                    if not country_selector:
                        logger.info("🔍 Ищу флажок по всей странице...")
                        try:
                            # Ищем элементы с российским флагом или +7
                            flag_candidates = await self.page.query_selector_all('*')
                            for candidate in flag_candidates[:50]:  # Проверяем первые 50
                                try:
                                    text = await candidate.inner_text()
                                    if text and ('+7' in text or 'RU' in text or '🇷🇺' in text):
                                        is_visible = await candidate.is_visible()
                                        if is_visible:
                                            logger.info(f"🎯 Найден элемент с +7: '{text[:30]}' - пробую как флажок")
                                            country_selector = candidate
                                            break
                                except:
                                    continue
                        except:
                            pass
                    
                    # ПОСЛЕДНЯЯ ПОПЫТКА: Клик по координатам слева от поля ввода
                    if not country_selector:
                        logger.info("🎯 Пробую кликнуть по координатам слева от поля ввода...")
                        try:
                            phone_field = await self.page.query_selector('input[data-testid="phone-input"]')
                            if phone_field:
                                # Получаем координаты поля ввода
                                box = await phone_field.bounding_box()
                                if box:
                                    # Кликаем слева от поля (примерно там где флажок)
                                    flag_x = box['x'] - 30  # 30 пикселей левее поля
                                    flag_y = box['y'] + box['height'] / 2  # По центру по высоте
                                    
                                    logger.info(f"🎯 Кликаю по координатам флажка: x={flag_x}, y={flag_y}")
                                    await self.page.mouse.click(flag_x, flag_y)
                                    await asyncio.sleep(3)
                                    
                                    # Проверяем появился ли выпадающий список
                                    dropdown_appeared = False
                                    dropdown_selectors = ['ul', 'div[role="listbox"]', '.dropdown', '[role="menu"]']
                                    for dropdown_sel in dropdown_selectors:
                                        dropdown = await self.page.query_selector(dropdown_sel)
                                        if dropdown and await dropdown.is_visible():
                                            logger.info(f"✅ Выпадающий список появился: {dropdown_sel}")
                                            dropdown_appeared = True
                                            break
                                    
                                    if dropdown_appeared:
                                        # Ищем Кыргызстан в появившемся списке
                                        kg_found = False
                                        kg_search_terms = ['996', 'Кыргыз', 'Kyrgyz', 'KG']
                                        for term in kg_search_terms:
                                            try:
                                                kg_element = await self.page.query_selector(f'text="{term}"')
                                                if not kg_element:
                                                    kg_element = await self.page.query_selector(f'[title*="{term}"]')
                                                if not kg_element:
                                                    kg_element = await self.page.query_selector(f'*:has-text("{term}")')
                                                
                                                if kg_element and await kg_element.is_visible():
                                                    await kg_element.click()
                                                    logger.info(f"✅ Кыргызстан выбран по термину: {term}")
                                                    kg_selected = True
                                                    kg_found = True
                                                    await asyncio.sleep(2)
                                                    break
                                            except:
                                                continue
                                        
                                        if not kg_found:
                                            logger.warning("⚠️ Кыргызстан не найден в выпадающем списке")
                                    else:
                                        logger.warning("⚠️ Выпадающий список не появился после клика")
                        except Exception as e:
                            logger.error(f"❌ Ошибка клика по координатам: {e}")
                
                if country_selector:
                    try:
                        logger.info(f"✅ Найден селектор страны, кликаю: {country_selector}")
                        
                        # ШАГ 1: Кликаем по флажку для открытия списка стран
                        await country_selector.click()
                        logger.info("🔽 Кликнул по флажку, ожидаю выпадающий список...")
                        await asyncio.sleep(3)  # Ждем открытия списка
                        
                        # ШАГ 2: Ищем Кыргызстан в выпадающем списке (расширенный поиск)
                        kg_options = [
                            # ПРИОРИТЕТ 1: WB SVG флаг Кыргызстана
                            'img[src*="country-flags/kg.svg"]',
                            'img[src*="/kg.svg"]',
                            '*:has(img[src*="country-flags/kg.svg"])',
                            'div:has(img[src*="/kg.svg"])',
                            'li:has(img[src*="/kg.svg"])',
                            'option:has(img[src*="/kg.svg"])',
                            
                            # По тексту названия страны
                            'text="Кыргызстан"',
                            'text="Киргизия"', 
                            'text="Kyrgyzstan"',
                            'text="Кыргыз"',
                            
                            # По коду страны +996
                            'text="+996"',
                            'text="996"',
                            'li:has-text("996")',
                            'option:has-text("996")',
                            'div:has-text("996")',
                            'span:has-text("996")',
                            
                            # По атрибутам
                            '[data-country="KG"]',
                            '[data-country="996"]',
                            '[data-code="996"]',
                            '[value="996"]',
                            '[title*="996"]',
                            '[alt*="Kyrgyz"]',
                            
                            # Комбинированный поиск
                            'li:has-text("Кыргыз")',
                            'div:has-text("Кыргыз")',
                            'option:has-text("Кыргыз")'
                        ]
                        
                        kg_selected_in_dropdown = False
                        for option_selector in kg_options:
                            try:
                                logger.info(f"🔍 Ищу Кыргызстан по селектору: {option_selector}")
                                kg_option = await self.page.query_selector(option_selector)
                                if kg_option:
                                    # Проверяем видимость элемента
                                    is_visible = await kg_option.is_visible()
                                    logger.info(f"📍 Найден элемент, видимый: {is_visible}")
                                    
                                    if is_visible:
                                        await kg_option.click()
                                        logger.info(f"✅ УСПЕШНО выбрана Киргизия: {option_selector}")
                                        kg_selected = True  # Обновляем основную переменную
                                        kg_selected_in_dropdown = True
                                        await asyncio.sleep(2)  # Ждем применения выбора
                                        break
                            except Exception as e:
                                logger.debug(f"⚠️ Ошибка с селектором {option_selector}: {e}")
                                continue
                        
                        if not kg_selected_in_dropdown:
                            logger.warning("⚠️ Не удалось найти Кыргызстан в списке стран")
                            logger.info("🔍 Попробую найти все доступные опции...")
                            
                            # Показываем все доступные опции для отладки
                            try:
                                all_options = await self.page.query_selector_all('li, option, div[role="option"]')
                                logger.info(f"📋 Найдено опций в списке: {len(all_options)}")
                                
                                for i, option in enumerate(all_options[:10]):  # Показываем первые 10
                                    try:
                                        text = await option.inner_text()
                                        if text and len(text.strip()) > 0:
                                            logger.info(f"  {i+1}. '{text.strip()}'")
                                    except:
                                        pass
                            except:
                                pass
                        else:
                            logger.info("🎯 Кыргызстан выбран, код страны должен измениться на +996")
                    
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка выбора региона: {e}")
                else:
                    logger.warning("⚠️ Не найден селектор выбора страны (флажок)")
            
            # 🚀 НОВАЯ ОХУЕННАЯ ЛОГИКА ВВОДА НОМЕРА ДЛЯ ВСЕХ СТРАН МИРА! 🚀
            logger.info(f"📱 Обрабатываю номер телефона: {phone}")
            
            # Парсим номер с помощью нашего охуенного парсера
            country_code, clean_number, country_name = self.parse_phone_number(phone)
            logger.info(f"🌍 Страна: {country_name}")
            logger.info(f"📱 Чистый номер для ввода: '{clean_number}'")
            
            # Стратегия ввода номера:
            # 1. Сначала пробуем ввести только чистый номер (без кода страны)
            # 2. Если не работает, пробуем полный номер
            # 3. Если и это не работает, пробуем разные варианты
            
            success = False
            
            # Попытка 1: Вводим только чистый номер (самый надежный способ)
            try:
                logger.info(f"📱 Попытка 1: Ввод чистого номера '{clean_number}' без кода страны")
                
                # Очищаем поле
                phone_element = await self.page.query_selector(phone_input)
                await phone_element.click()
                await phone_element.fill("")
                await asyncio.sleep(0.5)
                
                # Вводим чистый номер
                await self._human_type(phone_input, clean_number)
                await asyncio.sleep(1)
                
                # Проверяем что получилось
                current_value = await self.page.evaluate(f'document.querySelector(`{phone_input}`).value')
                logger.info(f"🔍 Значение в поле: '{current_value}'")
                
                # Если в поле есть наш номер, считаем успешным
                if clean_number in current_value or len(current_value) >= len(clean_number) - 1:
                    logger.info("✅ Попытка 1 успешна! Чистый номер введен корректно")
                    success = True
                else:
                    logger.warning("⚠️ Попытка 1 не удалась, пробую другие варианты...")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в попытке 1: {e}")
            
            # Попытка 2: Если первая не сработала, пробуем еще раз чистый номер
            if not success:
                try:
                    logger.info(f"📱 Попытка 2: Повторный ввод чистого номера '{clean_number}'")
                    
                    # Очищаем поле
                    phone_element = await self.page.query_selector(phone_input)
                    await phone_element.click()
                    await phone_element.fill("")
                    await asyncio.sleep(0.5)
                    
                    # Вводим чистый номер (БЕЗ кода страны, так как WB может его подставить автоматически)
                    await self._human_type(phone_input, clean_number)
                    await asyncio.sleep(1)
                    
                    # Проверяем результат
                    current_value = await self.page.evaluate(f'document.querySelector(`{phone_input}`).value')
                    logger.info(f"🔍 Значение в поле: '{current_value}'")
                    
                    # Если WB заменил код страны на неправильный, исправляем
                    if country_code != '+7' and ('+7' in current_value or current_value.startswith('7')):
                        logger.warning(f"⚠️ WB заменил {country_code} на +7, исправляю...")
                        
                        # Очищаем и вводим снова только цифры
                        await phone_element.click()
                        await phone_element.fill("")
                        await asyncio.sleep(0.5)
                        await self._human_type(phone_input, clean_number)
                        await asyncio.sleep(1)
                        
                        final_value = await self.page.evaluate(f'document.querySelector(`{phone_input}`).value')
                        logger.info(f"🔍 Исправленное значение: '{final_value}'")
                        
                    logger.info("✅ Попытка 2 выполнена")
                    success = True
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в попытке 2: {e}")
            
            # Попытка 3: Если ничего не работает, пробуем альтернативные варианты
            if not success:
                logger.warning("⚠️ Стандартные попытки не сработали, пробую альтернативные варианты...")
                
                try:
                    # Для российских номеров пробуем разные форматы
                    # ВАЖНО: WB автоматически подставляет "+7", поэтому вводим БЕЗ кода страны
                    if country_code == '+7':
                        variants = [
                            clean_number,  # 9001234567 - основной вариант
                            clean_number.replace(clean_number[0], '8', 1) if clean_number.startswith('9') else clean_number,  # 8001234567
                        ]
                    else:
                        variants = [
                            clean_number,
                            f"{country_code[1:]}{clean_number}",  # код без + и номер
                            f"{country_code}{clean_number}"  # полный номер
                        ]
                    
                    for i, variant in enumerate(variants, 3):
                        logger.info(f"📱 Попытка {i}: Ввод варианта '{variant}'")
                        
                        phone_element = await self.page.query_selector(phone_input)
                        await phone_element.click()
                        await phone_element.fill("")
                        await asyncio.sleep(0.5)
                        await self._human_type(phone_input, variant)
                        await asyncio.sleep(1)
                        
                        current_value = await self.page.evaluate(f'document.querySelector(`{phone_input}`).value')
                        logger.info(f"🔍 Значение: '{current_value}'")
                        
                        if len(current_value) >= 10:  # Если в поле достаточно цифр
                            logger.info(f"✅ Попытка {i} успешна!")
                            success = True
                            break
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка в альтернативных попытках: {e}")
            
            if success:
                logger.info(f"🎉 НОМЕР УСПЕШНО ВВЕДЕН! Страна: {country_name}")
            else:
                logger.warning("⚠️ Не удалось ввести номер идеально, но продолжаю...")
            
            # Ждем немного
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Ищем кнопку отправки
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Войти")',
                'button:has-text("Получить код")',
                'button:has-text("Далее")',
                'input[type="submit"]',
                '.submit-btn',
                '.login-btn',
                'form button:last-of-type'
            ]
            
            submit_btn = None
            for selector in submit_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        submit_btn = selector
                        logger.info(f"✅ Найдена кнопка отправки: {selector}")
                        break
                except:
                    continue
            
            if submit_btn:
                logger.info("🔘 Нажимаю кнопку отправки SMS")
                await self._human_click(submit_btn)
            else:
                # Пробуем Enter
                logger.info("⌨️ Нажимаю Enter для отправки")
                await self.page.keyboard.press('Enter')
            
            # УВЕЛИЧИВАЕМ ВРЕМЯ ОЖИДАНИЯ - WB может долго обрабатывать запрос
            logger.info("⏳ Ожидаю ответ от WB (может занять до 10 секунд)...")
            await asyncio.sleep(random.uniform(5, 8))
            
            # Проверяем результат несколько раз
            sms_sent = False
            for attempt in range(4):  # 4 попытки проверки
                logger.info(f"🔍 Проверка отправки SMS: попытка {attempt + 1}/4")
                
                # Расширенные индикаторы успешной отправки SMS
                sms_indicators = [
                    'input[name="code"]',
                    'input[name="smsCode"]', 
                    'input[name="verificationCode"]',
                    'input[data-testid*="code"]',
                    'input[placeholder*="код" i]',
                    'input[placeholder*="code" i]',
                    'input[maxlength="4"]',
                    'input[maxlength="6"]',
                    'text=код отправлен',
                    'text=SMS отправлен',
                    'text=Введите код',
                    'text=код из SMS',
                    '.sms-code',
                    '.verification-code',
                    '.code-input'
                ]
                
                for indicator in sms_indicators:
                    try:
                        element = await self.page.query_selector(indicator)
                        if element and (await element.is_visible() if hasattr(element, 'is_visible') else True):
                            logger.info(f"✅ Найден индикатор SMS: {indicator}")
                            sms_sent = True
                            break
                    except:
                        continue
                
                if sms_sent:
                    break
                    
                # Проверяем изменение URL (возможный редирект)
                current_url = self.page.url
                if "code" in current_url.lower() or "sms" in current_url.lower() or "verification" in current_url.lower():
                    logger.info(f"✅ Обнаружен редирект на страницу ввода кода: {current_url}")
                    sms_sent = True
                    break
                
                # Проверяем текст на странице
                try:
                    page_text = await self.page.inner_text('body')
                    success_phrases = ["код отправлен", "sms отправлен", "введите код", "код из sms", "verification code"]
                    for phrase in success_phrases:
                        if phrase.lower() in page_text.lower():
                            logger.info(f"✅ Найдена фраза подтверждения: {phrase}")
                            sms_sent = True
                            break
                    if sms_sent:
                        break
                except:
                    pass
                
                # Ждем перед следующей попыткой (кроме последней)
                if attempt < 3:
                    await asyncio.sleep(2)
            
            if sms_sent:
                logger.info("✅ SMS код запрошен успешно")
                await self._save_cookies()
                return True
            else:
                logger.warning("⚠️ Не удалось определить отправку SMS, но продолжаю...")
                logger.info(f"🔍 Текущий URL: {self.page.url}")
                logger.info(f"🔍 Заголовок: {await self.page.title()}")
                
                # Сохраняем скриншот для отладки
                if self.debug_mode:
                    await self.page.screenshot(path="wb_sms_debug.png")
                    logger.info("📸 Скриншот для отладки: wb_sms_debug.png")
                
                # Возвращаем True чтобы дать пользователю шанс ввести код
                await self._save_cookies()
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка ввода номера телефона: {e}")
            return False
    
    async def login_step2_sms(self, sms_code: str) -> bool:
        """Шаг 2: Ввод SMS кода."""
        try:
            logger.info(f"📨 Ввожу SMS код: {sms_code}")
            
            # Ищем поле SMS кода (приоритет для WB)
            sms_selectors = [
                # Специфичные селекторы WB
                'input[data-testid*="code"]',
                'input[data-testid*="sms"]',
                'input[data-testid*="verification"]',
                '.CodeInputContentView input',
                '.code-input input',
                
                # Общие селекторы
                'input[name="code"]',
                'input[name="smsCode"]',
                'input[name="verificationCode"]',
                'input[placeholder*="код" i]',
                'input[placeholder*="code" i]',
                'input[type="text"]:not([name="phone"])',
                'input[maxlength="4"]',
                'input[maxlength="6"]',
                
                # Поиск в модальных окнах
                '.modal input[type="text"]',
                '#Portal-modal input[type="text"]',
                '.Portal-modal input[type="text"]',
                
                # Последние варианты
                '.sms-code input',
                'form input:last-of-type'
            ]
            
            sms_input = None
            for selector in sms_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        sms_input = selector
                        logger.info(f"✅ Найдено поле SMS кода: {selector}")
                        break
                except:
                    continue
            
            if not sms_input:
                logger.error("❌ Не найдено поле для ввода SMS кода")
                return False
            
            # Прямой ввод SMS кода (без клика, так как поле может быть перекрыто)
            logger.info(f"📝 Ввожу SMS код напрямую в поле: {sms_input}")
            
            try:
                # Получаем элемент поля
                sms_field = await self.page.query_selector(sms_input)
                if sms_field:
                    # Кликаем на поле для фокуса
                    await sms_field.click()
                    await asyncio.sleep(0.5)
                    
                    # Полностью очищаем поле (Ctrl+A + Delete)
                    await sms_field.press('Control+a')
                    await asyncio.sleep(0.2)
                    await sms_field.press('Delete')
                    await asyncio.sleep(0.5)
                    
                    # Проверяем, что поле действительно пустое
                    current_value = await sms_field.input_value()
                    if current_value:
                        logger.warning(f"⚠️ Поле не очистилось полностью, текущее значение: '{current_value}'")
                        # Дополнительная очистка
                        await sms_field.fill("")
                        await asyncio.sleep(0.3)
                    
                    # Вводим код целиком (более надежный способ)
                    logger.info(f"⌨️ Ввожу SMS код: {sms_code}")
                    await sms_field.fill(sms_code)
                    await asyncio.sleep(0.5)
                    
                    # Проверяем, что код введен правильно
                    final_value = await sms_field.input_value()
                    if final_value == sms_code:
                        logger.info(f"✅ SMS код введен правильно: {sms_code}")
                    else:
                        logger.warning(f"⚠️ Код введен неправильно! Ожидался: '{sms_code}', получен: '{final_value}'")
                        # Пробуем еще раз через type
                        await sms_field.fill("")
                        await asyncio.sleep(0.3)
                        for char in sms_code:
                            await sms_field.type(char)
                            await asyncio.sleep(random.uniform(0.1, 0.2))
                        
                        # Финальная проверка
                        final_value = await sms_field.input_value()
                        logger.info(f"🔄 После повторного ввода: '{final_value}'")
                    
                else:
                    logger.error("❌ Не удалось получить элемент поля SMS")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка ввода SMS кода: {e}")
                # Запасной вариант - через JavaScript
                try:
                    logger.info("🔄 Пробую ввести код через JavaScript...")
                    await self.page.evaluate(f"""
                        const input = document.querySelector('{sms_input}');
                        if (input) {{
                            input.value = '{sms_code}';
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    """)
                    logger.info("✅ SMS код введен через JavaScript")
                except Exception as js_error:
                    logger.error(f"❌ Ошибка JavaScript ввода: {js_error}")
                    return False
            
            # Ждем автоотправки или нажимаем кнопку
            await asyncio.sleep(random.uniform(1, 2))
            
            # Ищем кнопку подтверждения
            confirm_selectors = [
                'button[type="submit"]',
                'button:has-text("Войти")',
                'button:has-text("Подтвердить")',
                'button:has-text("Далее")',
                'form button:last-of-type'
            ]
            
            confirm_btn = None
            for selector in confirm_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        confirm_btn = selector
                        break
                except:
                    continue
            
            if confirm_btn:
                logger.info("🔘 Нажимаю кнопку подтверждения")
                await self._human_click(confirm_btn)
            else:
                logger.info("⌨️ Нажимаю Enter для подтверждения")
                await self.page.keyboard.press('Enter')
            
            # Ждем перенаправления или проверки email
            await asyncio.sleep(random.uniform(3, 5))
            
            # Проверяем, не требуется ли подтверждение по email
            current_url = self.page.url
            logger.info(f"🔍 Текущий URL после SMS: {current_url}")
            
            # Проверяем наличие email подтверждения
            email_verification_detected = await self._check_email_verification()
            if email_verification_detected:
                logger.warning("📧 Обнаружено требование подтверждения по email!")
                # Возвращаем специальный код для обработки email
                return "email_required"
            
            # Проверяем успешный вход
            current_url = self.page.url
            login_success = any([
                'seller.wildberries.ru' in current_url and 'login' not in current_url,
                'cabinet' in current_url,
                'dashboard' in current_url,
                'supplies' in current_url
            ])
            
            if login_success:
                logger.info("🎉 Успешный вход в WB!")
                await self._save_cookies()
                
                # Обновляем данные в БД о успешном входе
                if self.user_id:
                    await db_service.update_browser_session_login_success(self.user_id, sms_code[:4] if sms_code else "unknown")
                    logger.info(f"💾 Обновлена БД: успешный вход пользователя {self.user_id}")
                
                # Переходим на страницу управления поставками
                supplies_url = "https://seller.wildberries.ru/supplies-management/all-supplies"
                logger.info(f"🚚 Переходим на страницу поставок: {supplies_url}")
                
                try:
                    await self.page.goto(supplies_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(random.uniform(3, 5))  # Ждем загрузки страницы
                    
                    final_url = self.page.url
                    if "supplies-management" in final_url:
                        logger.info(f"✅ Успешно перешли на страницу поставок: {final_url}")
                    else:
                        logger.warning(f"⚠️ Не удалось перейти на страницу поставок. URL: {final_url}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка перехода на страницу поставок: {e}")
                
                return True
            else:
                logger.warning(f"⚠️ Возможная ошибка входа. URL: {current_url}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка ввода SMS кода: {e}")
            
            # Обновляем БД о неудачной попытке входа
            if self.user_id:
                await db_service.update_browser_session_login_failed(self.user_id)
                logger.info(f"💾 Обновлена БД: неудачная попытка входа пользователя {self.user_id}")
            
            return False
    
    async def _check_email_verification(self) -> bool:
        """Проверяет, требуется ли подтверждение по email."""
        try:
            logger.info("📧 Проверяю наличие email верификации...")
            
            # Селекторы для проверки email верификации
            email_selectors = [
                # Тексты, указывающие на необходимость email подтверждения
                'text="Подтвердите адрес электронной почты"',
                'text="Проверьте электронную почту"',
                'text="На вашу почту отправлено письмо"',
                'text="Подтверждение по электронной почте"',
                
                # Поля для ввода email кода
                'input[placeholder*="код" i][placeholder*="почт" i]',
                'input[placeholder*="email" i][placeholder*="код" i]',
                'input[name*="email" i][name*="code" i]',
                
                # Кнопки связанные с email
                'button:has-text("Отправить код на почту")',
                'button:has-text("Подтвердить email")',
                
                # Общие селекторы
                '[data-testid*="email"]',
                '.email-verification',
                '#email-verification'
            ]
            
            for selector in email_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.warning(f"📧 Найден элемент email верификации: {selector}")
                        return True
                except:
                    continue
            
            # Проверяем URL на наличие email-related параметров
            current_url = self.page.url
            email_url_indicators = ['email', 'verification', 'confirm', 'check-email']
            for indicator in email_url_indicators:
                if indicator in current_url.lower():
                    logger.warning(f"📧 URL указывает на email верификацию: {current_url}")
                    return True
            
            # Проверяем текст на странице
            page_content = await self.page.content()
            email_text_indicators = [
                'проверьте электронную почту',
                'подтвердите адрес электронной почты',
                'на вашу почту отправлено',
                'email verification',
                'check your email'
            ]
            
            for indicator in email_text_indicators:
                if indicator.lower() in page_content.lower():
                    logger.warning(f"📧 Найден текст email верификации: {indicator}")
                    return True
            
            logger.info("✅ Email верификация не требуется")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки email верификации: {e}")
            return False
    
    async def navigate_to_supplies(self) -> bool:
        """Переход к разделу поставок."""
        try:
            logger.info("📦 Перехожу к разделу поставок...")
            
            # Возможные URL для поставок
            supplies_urls = [
                "https://seller.wildberries.ru/supplies",
                "https://seller.wildberries.ru/supplies/new",
                "https://seller.wildberries.ru/cabinet/supplies"
            ]
            
            for url in supplies_urls:
                try:
                    response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
                    if response and response.status == 200:
                        logger.info(f"✅ Перешел к поставкам: {url}")
                        await asyncio.sleep(random.uniform(2, 3))
                        return True
                except:
                    continue
            
            # Если прямые ссылки не работают, ищем через меню
            menu_selectors = [
                'a[href*="supplies"]',
                'text=Поставки',
                'text=Склад и поставки',
                '.menu a:has-text("Поставки")'
            ]
            
            for selector in menu_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await self._human_click(selector)
                        await asyncio.sleep(random.uniform(2, 3))
                        logger.info("✅ Перешел к поставкам через меню")
                        return True
                except:
                    continue
            
            logger.error("❌ Не удалось перейти к разделу поставок")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка перехода к поставкам: {e}")
            return False
    
    async def book_supply_slot(self, supply_id: str, date: str, time_slot: str) -> bool:
        """Бронирование слота для поставки."""
        try:
            logger.info(f"🎯 Бронирую слот для поставки {supply_id} на {date} {time_slot}")
            
            # Переходим к конкретной поставке
            supply_url = f"https://seller.wildberries.ru/supplies/{supply_id}"
            await self.page.goto(supply_url, wait_until="networkidle")
            
            # Ищем календарь или кнопку бронирования
            booking_selectors = [
                f'button:has-text("{date}")',
                f'[data-date="{date}"]',
                '.calendar-day',
                '.time-slot',
                'button:has-text("Забронировать")'
            ]
            
            for selector in booking_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await self._human_click(selector)
                        logger.info(f"✅ Выбрал элемент: {selector}")
                        break
                except:
                    continue
            
            # Подтверждаем бронирование
            confirm_selectors = [
                'button:has-text("Подтвердить")',
                'button:has-text("Забронировать")',
                'button[type="submit"]'
            ]
            
            for selector in confirm_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await self._human_click(selector)
                        logger.info("✅ Подтвердил бронирование")
                        break
                except:
                    continue
            
            # Ждем результата
            await asyncio.sleep(random.uniform(2, 4))
            
            # Проверяем успех бронирования
            success_indicators = [
                'text=успешно забронирован',
                'text=слот забронирован',
                '.success-message',
                '.booking-success'
            ]
            
            for indicator in success_indicators:
                try:
                    if await self.page.query_selector(indicator):
                        logger.info("🎉 Слот успешно забронирован!")
                        return True
                except:
                    continue
            
            logger.warning("⚠️ Не удалось определить результат бронирования")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка бронирования слота: {e}")
            return False
    
    async def close_browser(self):
        """Закрытие браузера с сохранением сессии."""
        try:
            if self.page:
                await self._save_cookies()
            
            # При использовании persistent context, закрываем только браузер/контекст
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("🔚 Браузер закрыт, сессия сохранена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия браузера: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
    
    async def get_current_url(self) -> str:
        """Получить текущий URL."""
        if self.page:
            return self.page.url
        return ""
    
    async def take_screenshot(self, filename: str = "screenshot.png") -> bool:
        """Сделать скриншот в папку браузера."""
        try:
            if self.page:
                # МУЛЬТИБРАУЗЕРНЫЕ СКРИНШОТЫ! Каждый в свою папку
                screenshot_path = self.screenshots_dir / filename
                await self.page.screenshot(path=str(screenshot_path), full_page=True)
                if self.user_id:
                    logger.info(f"📸 Скриншот браузера {self.user_id} сохранен: {screenshot_path}")
                else:
                    logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
                return True
        except Exception as e:
            logger.error(f"❌ Ошибка создания скриншота: {e}")
            return False
    
    async def book_supply_by_id(self, supply_id: str, preorder_id: str = None, min_hours_ahead: int = 80, custom_date: str = None, use_max_coefficient: bool = False, target_coefficient: float = None, selected_dates: list = None) -> Dict[str, Any]:
        """
        ОХУЕННОЕ бронирование поставки по ID через прямую ссылку.
        
        Args:
            supply_id: ID поставки для бронирования
            preorder_id: ID предзаказа (опционально)
            min_hours_ahead: минимальное количество часов вперед для бронирования (по умолчанию 80)
            custom_date: Кастомная дата для бронирования (формат: 'DD.MM.YYYY' или 'YYYY-MM-DD')
            use_max_coefficient: Если True, выбирает дату с максимальным коэффициентом
            target_coefficient: Максимальный допустимый коэффициент (ищет коэффициент <= этого значения)
            selected_dates: Список дат выбранных пользователем для проверки коэффициента
        
        Returns:
            Dict с результатом бронирования, включая детали (дата, склад, коэффициент)
        """
        result = {
            "success": False,
            "message": "",
            "booked_date": None,
            "supply_id": supply_id,
            "attempts": 0
        }
        
        try:
            logger.info(f"🚀 НАЧИНАЮ ОХУЕННОЕ БРОНИРОВАНИЕ! Supply ID: {supply_id}, Preorder ID: {preorder_id}")
            
            # Шаг 1: Проверяем авторизацию через сессию
            if self.user_id and await self.should_skip_login():
                logger.info("✅ Сессия валидна, пропускаю вход")
            else:
                # Если не авторизованы - возвращаем ошибку (логин должен быть выполнен заранее)
                if not await self.check_if_logged_in():
                    result["message"] = "❌ Не авторизован! Сначала выполните вход в систему"
                    return result
            
            # Шаг 2: Формируем URL и переходим напрямую к поставке
            # Для незабронированных поставок используем supplyId в параметре preorderId
            supply_url = f"https://seller.wildberries.ru/supplies-management/all-supplies/supply-detail?preorderId={supply_id}&supplyId"
            
            logger.info(f"🔗 Перехожу по прямой ссылке: {supply_url}")
            
            response = await self.page.goto(supply_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(8)  # БЛЯДЬ! НАМНОГО БОЛЬШЕ ВРЕМЕНИ для React приложения!
            
            if not response or response.status != 200:
                result["message"] = f"❌ Не удалось открыть страницу поставки (статус: {response.status if response else 'нет ответа'})"
                return result
            
            logger.info("✅ Страница поставки загружена")
            
            # АКТИВНОЕ ОЖИДАНИЕ ЗАГРУЗКИ REACT ПРИЛОЖЕНИЯ!
            logger.info("⏳ Жду полной загрузки React приложения...")
            
            react_loaded = False
            for attempt in range(20):  # 20 попыток по 1 секунде = 20 секунд максимум
                await asyncio.sleep(1)
                
                # Проверяем что React приложение загрузилось
                react_elements = await self.page.locator('button, [class*="button"], [data-testid]').count()
                
                if react_elements > 10:  # Достаточно элементов = приложение загрузилось
                    react_loaded = True
                    logger.info(f"🎯 REACT ЗАГРУЗИЛСЯ! Попытка {attempt + 1}, найдено элементов: {react_elements}")
                    break
                else:
                    logger.info(f"⏳ React еще грузится... Попытка {attempt + 1}/20, найдено элементов: {react_elements}")
            
            if not react_loaded:
                logger.warning("⚠️ React приложение так и не загрузилось полностью за 20 секунд!")
            
            # Блокируем аналитику и детекцию автоматизации WB
            await self.page.evaluate("""
                // Блокируем WB аналитический SDK
                if (window.wba) {
                    window.wba = function() { return false; };
                }
                
                // Блокируем отправку аналитических данных
                if (window.navigator && window.navigator.sendBeacon) {
                    const originalSendBeacon = window.navigator.sendBeacon;
                    window.navigator.sendBeacon = function(url, data) {
                        if (url && (url.includes('a.wb.ru') || url.includes('wbbasket.ru'))) {
                            return false; // Блокируем только аналитику
                        }
                        return originalSendBeacon.apply(this, arguments);
                    };
                }
                
                // КРИТИЧНО: Маскируем автоматизацию (максимально безопасно)
                try {
                    if ('webdriver' in navigator) {
                        delete navigator.webdriver;
                    }
                } catch (e) {
                    try {
                        navigator.webdriver = undefined;
                    } catch (e2) {
                        // Игнорируем все ошибки webdriver - не критично
                        console.log('Webdriver изменить не удалось, игнорируем');
                    }
                }
                
                // Убираем следы Playwright
                delete window.chrome;
                delete window.navigator.webdriver;
                delete window.__playwright;
                delete window.__pw_manual;
                
                // Блокируем детекцию WB
                if (window.WB) {
                    window.WB.isAutomation = function() { return false; };
                    window.WB.detectBot = function() { return false; };
                    window.WB.captcha = { show: function() {} };
                    delete window.WB._automation_detected;
                    delete window.WB._click_blocked;
                }
                
                // НЕ БЛОКИРУЕМ addEventListener - это убивает модальные окна!
                // Просто блокируем только beforeunload события
                window.addEventListener('beforeunload', function(e) { e.preventDefault(); return false; }, true);
                
                // Блокируем XMLHttpRequest только для аналитики
                const originalXHR = window.XMLHttpRequest;
                window.XMLHttpRequest = function() {
                    const xhr = new originalXHR();
                    const originalOpen = xhr.open;
                    xhr.open = function(method, url) {
                        if (url && (url.includes('a.wb.ru') || url.includes('wbbasket.ru'))) {
                            return false; // Блокируем только аналитику
                        }
                        return originalOpen.apply(this, arguments);
                    };
                    return xhr;
                };
                
                // Блокируем fetch только для аналитики
                const originalFetch = window.fetch;
                window.fetch = function(url, options) {
                    if (url && (url.includes('a.wb.ru') || url.includes('wbbasket.ru'))) {
                        return Promise.resolve(new Response('{}'));
                    }
                    return originalFetch.apply(this, arguments);
                };
            """)
            logger.info("✅ Аналитические скрипты WB заблокированы (React функциональность сохранена)")
            
            # Максимум 3 попытки бронирования
            max_attempts = 3
            
            for attempt in range(1, max_attempts + 1):
                result["attempts"] = attempt
                logger.info(f"🎯 Попытка бронирования #{attempt}")
                
                # КРИТИЧНО: Сброс состояния страницы перед каждой попыткой
                if attempt > 1:
                    logger.info("🔄 Сбрасываю состояние страницы для избежания блокировок...")
                    try:
                        # Полная очистка состояния браузера
                        await self.page.evaluate("""
                            // Очищаем все переменные автоматизации (безопасно)
                            try { delete window.webdriver; } catch(e) {}
                            try { delete window._phantom; } catch(e) {}
                            try { delete window.callPhantom; } catch(e) {}
                            try { delete window.chrome; } catch(e) {}
                            try { delete window.navigator.webdriver; } catch(e) {}
                            try { navigator.webdriver = undefined; } catch(e) {}
                            
                            // НЕ ОЧИЩАЕМ event listeners - это ломает модальные окна!
                            
                            // Сбрасываем флаги WB
                            if (window.WB) {
                                delete window.WB._automation_detected;
                                delete window.WB._bot_detected;
                            }
                            
                            // НЕ ОЧИЩАЕМ localStorage и sessionStorage для сохранения логина
                            // Только очищаем специфичные флаги автоматизации без удаления авторизации
                            try {
                                localStorage.removeItem('__playwright_automation__');
                                localStorage.removeItem('__bot_detected__');
                                sessionStorage.removeItem('__playwright_automation__');
                                sessionStorage.removeItem('__bot_detected__');
                            } catch(e) {}
                        """)
                        
                        # НЕ ПЕРЕЗАГРУЖАЕМ страницу для сохранения логина
                        # Небольшая пауза для применения изменений
                        await asyncio.sleep(0.5)
                        
                        # Переходим на нужную поставку заново
                        supply_url = f"https://seller.wildberries.ru/supplies-management/all?query={supply_id}"
                        await self.page.goto(supply_url, wait_until='networkidle')
                        await asyncio.sleep(10)  # БЛЯДЬ! ЕЩЕ БОЛЬШЕ ВРЕМЕНИ после перезагрузки!
                        
                        logger.info("✅ Состояние страницы успешно сброшено")
                        
                    except Exception as reset_error:
                        logger.warning(f"⚠️ Ошибка сброса состояния: {reset_error}")
                
                # Шаг 3: Ищем кнопку "Забронировать поставку"
                book_button = None
                button_texts = [
                    "Запланировать поставку",  # Точный текст из HTML  
                    "Забронировать поставку",
                    "Забронировать",
                    "Запланировать",
                    "Выбрать дату",
                    # Локализационные ключи
                    "common-translates.planSupply",
                    "common-translates.bookSupply",
                    "common-translates.plan",
                    "common-translates.book"
                ]
                
                for btn_text in button_texts:
                    try:
                        # Ищем кнопку по тексту
                        button_selector = f'button:has-text("{btn_text}")'
                        book_button = self.page.locator(button_selector).first
                        
                        if await book_button.count() > 0 and await book_button.is_visible():
                            logger.info(f"✅ Найдена кнопка: {btn_text}")
                            break
                            
                        # Также проверяем span внутри button
                        span_selector = f'button span:has-text("{btn_text}")'
                        book_button = self.page.locator(span_selector).locator('..')
                        
                        if await book_button.count() > 0 and await book_button.is_visible():
                            logger.info(f"✅ Найдена кнопка через span: {btn_text}")
                            break
                    except:
                        continue
                
                # Если кнопка не найдена по тексту, ищем по селекторам классов
                if not book_button or await book_button.count() == 0:
                    logger.info("🔍 Ищу кнопку бронирования по селекторам классов...")
                    class_selectors = [
                        # ТОЧНЫЙ селектор из предоставленного HTML
                        'span[class*="caption__kqFcIewCT5"]:has-text("Запланировать поставку")',
                        'button:has(span[class*="caption__kqFcIewCT5"])',
                        # Общие селекторы
                        'button[class*="book"]',
                        'button[class*="plan"]',
                        'button[class*="schedule"]',
                        'button[class*="booking"]',
                        'button[class*="supply"]',
                        '[data-testid*="book"]',
                        '[data-testid*="plan"]',
                        '[data-testid*="schedule"]',
                        'button[class*="primary"]',
                        'button[class*="main"]',
                        'button[class*="action"]'
                    ]
                    
                    for selector in class_selectors:
                        try:
                            book_button = self.page.locator(selector).first
                            if await book_button.count() > 0 and await book_button.is_visible():
                                logger.info(f"✅ Найдена кнопка по селектору: {selector}")
                                break
                        except:
                            continue
                
                if not book_button or await book_button.count() == 0:
                    logger.error("❌ Кнопка 'Забронировать поставку' не найдена")
                    await self.take_screenshot(f"no_book_button_attempt_{attempt}.png")
                    
                    # Пробуем обновить страницу и повторить
                    if attempt < max_attempts:
                        logger.info("🔄 Обновляю страницу...")
                        await self.page.reload(wait_until="domcontentloaded")
                        await asyncio.sleep(3)
                        continue
                    else:
                        result["message"] = "❌ Кнопка бронирования не найдена после всех попыток"
                        return result
                
                # Кликаем на кнопку бронирования с эмуляцией человеческого поведения
                try:
                    # Добавляем случайную задержку перед кликом (как человек думает)
                    import random
                    human_delay = random.uniform(0.8, 2.0)
                    await asyncio.sleep(human_delay)
                    
                    # Очищаем возможные блокировки WB перед кликом
                    await self.page.evaluate("""
                        // Убираем детекцию автоматизации (безопасно)
                        try {
                            if ('webdriver' in navigator) {
                                delete navigator.webdriver;
                            }
                        } catch (e) {
                            navigator.webdriver = undefined;
                        }
                        try { delete window.chrome; } catch (e) {}
                        try { delete window.navigator.webdriver; } catch (e) {}
                        
                        // Сбрасываем флаги WB
                        if (window.WB) {
                            delete window.WB._click_blocked;
                            delete window.WB._automation_flag;
                        }
                    """)
                    
                    # Сначала наводимся на кнопку (как человек)
                    try:
                        await book_button.hover(timeout=2000, force=True)
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                    except Exception as hover_error:
                        logger.warning(f"⚠️ Ошибка наведения на кнопку бронирования: {hover_error}")
                        # Продолжаем без наведения
                    
                    # Прокручиваем к кнопке если нужно
                    await book_button.scroll_into_view_if_needed()
                    await asyncio.sleep(0.4)
                    
                    # Человекоподобный JavaScript клик
                    await book_button.evaluate("""
                        button => {
                            // Убираем все блокировки с кнопки
                            button.disabled = false;
                            button.style.pointerEvents = 'auto';
                            
                            // Получаем координаты кнопки
                            const rect = button.getBoundingClientRect();
                            const x = rect.left + rect.width / 2;
                            const y = rect.top + rect.height / 2;
                            
                            // Создаем человекоподобную последовательность событий с задержками
                            setTimeout(() => {
                                // Mouseover
                                button.dispatchEvent(new MouseEvent('mouseover', { 
                                    bubbles: true, clientX: x, clientY: y 
                                }));
                            }, 0);
                            
                            setTimeout(() => {
                                // Mousedown
                                button.dispatchEvent(new MouseEvent('mousedown', { 
                                    bubbles: true, clientX: x, clientY: y 
                                }));
                            }, 50);
                            
                            setTimeout(() => {
                                // Mouseup
                                button.dispatchEvent(new MouseEvent('mouseup', { 
                                    bubbles: true, clientX: x, clientY: y 
                                }));
                            }, 150);
                            
                            setTimeout(() => {
                                // Click
                                button.dispatchEvent(new MouseEvent('click', { 
                                    bubbles: true, clientX: x, clientY: y 
                                }));
                                
                                // Также обычный клик
                                button.click();
                            }, 200);
                        }
                    """)
                    logger.info("✅ Кликнул на кнопку бронирования с эмуляцией человека")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка человекоподобного клика: {e}")
                    # Fallback на простой клик
                    try:
                        await book_button.click()
                        logger.info("✅ Кликнул на кнопку бронирования через Playwright")
                    except Exception as e2:
                        logger.error(f"❌ Ошибка клика на кнопку: {e2}")
                        if attempt < max_attempts:
                            continue
                        else:
                            # Очищаем HTML теги из ошибки
                            import html
                            clean_error = html.escape(str(e2))
                            result["message"] = f"❌ Ошибка клика на кнопку: {clean_error}"
                            return result
                
                # Ждем загрузки JavaScript и появления popup
                await asyncio.sleep(5)  # Увеличиваем время ожидания для React приложения
                
                # Ждем загрузки React приложения (не используем networkidle для SPA)
                try:
                    # Ждем появления React root элемента
                    await self.page.wait_for_selector('#root', timeout=15000)
                    logger.info("✅ React приложение загружено")
                    
                    # Ждем загрузки React компонентов
                    await asyncio.sleep(3)
                    
                    # Проверяем, что страница полностью загружена
                    await self.page.wait_for_function("document.readyState === 'complete'", timeout=10000)
                    logger.info("✅ Страница полностью загружена")
                    
                    # Дополнительная блокировка аналитики после клика (только для предотвращения перехвата)
                    await self.page.evaluate("""
                        // Дополнительно блокируем WB аналитический SDK если он загрузился после клика
                        if (window.wba) {
                            window.wba = function() { return false; };
                        }
                    """)
                    logger.info("✅ Дополнительная блокировка аналитики применена")
                    
                except Exception as e:
                    logger.warning(f"⚠️ React приложение не загрузилось полностью: {e}, продолжаю...")
                
                # Ждем появления popup окна с календарем (React Portal)
                calendar_appeared = False
                calendar_selectors = [
                    '[id*="Portal-CalendarPlanModal"]',
                    '[class*="Portal-CalendarPlanModal"]',
                    '[class*="Calendar"]',
                    '[class*="calendar"]',
                    '[class*="date-picker"]',
                    '[class*="modal"]',
                    '[role="dialog"]',
                    '.date-selection',
                    '[data-testid="date-selector"]',
                    '#portal [class*="modal"]',
                    '#portal [class*="Calendar"]'
                ]
                
                # Ждем появления popup с увеличенным таймаутом для React
                for selector in calendar_selectors:
                    try:
                        await self.page.wait_for_selector(selector, timeout=12000)
                        calendar_appeared = True
                        logger.info(f"✅ Popup с календарем появился: {selector}")
                        break
                    except:
                        continue
                
                # Дополнительная проверка - ждем появления элементов внутри popup
                if not calendar_appeared:
                    # Пробуем найти любые модальные окна в portal
                    try:
                        portal_element = self.page.locator('#portal')
                        if await portal_element.count() > 0:
                            # Ищем любые модальные окна в portal
                            modal_in_portal = portal_element.locator('[class*="modal"], [class*="Modal"], [role="dialog"]')
                            if await modal_in_portal.count() > 0:
                                calendar_appeared = True
                                logger.info("✅ Найдено модальное окно в portal")
                    except:
                        pass
                
                # Дополнительная проверка - ждем появления элементов внутри popup
                if calendar_appeared:
                    # Ждем появления элементов календаря внутри popup
                    calendar_elements_selectors = [
                        '[data-testid*="calendar-cell"]',
                        '[class*="Calendar-cell"]',
                        'button[class*="Calendar-cell"]',
                        'div[class*="calendar-cell"]'
                    ]
                    
                    for selector in calendar_elements_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=5000)
                            logger.info(f"✅ Элементы календаря загружены: {selector}")
                            break
                        except:
                            continue
                
                if not calendar_appeared:
                    logger.warning("⚠️ Календарь не появился, но продолжаю искать даты...")
                
                # Шаг 4: Ищем доступные даты в popup окне
                await asyncio.sleep(2)  # УМЕНЬШИЛ С 3 ДО 2 СЕКУНД!
                
                # Ищем доступные даты для бронирования
                date_found = False
                selected_date = None
                
                # Селекторы для поиска доступных дат в календаре WB
                date_selectors = [
                    # ТОЧНЫЙ селектор из предоставленного HTML
                    'div[class*="Calendar-cell__date-container"][data-testid*="calendar-cell-date"]',
                    '[data-testid*="calendar-cell-date"]:not([class*="disabled"])',
                    # Оригинальные селекторы
                    '[data-testid*="calendar-cell"]:not([class*="disabled"])',
                    '[data-testid*="calendar-cell-amount"]',
                    'div[class*="Calendar-cell"]:not([class*="disabled"])',
                    'button[class*="Calendar-cell"]:not([disabled])',
                    'div[class*="calendar-cell"]:not([class*="disabled"])',
                    'button[class*="available"]:not([disabled])',
                    'div[class*="available"]:not([class*="disabled"])',
                    'td[class*="available"]:not([class*="disabled"])',
                    '[data-available="true"]',
                    '.date-item:not(.disabled)',
                    'button.date:not([disabled])',
                    # Новые селекторы для ячеек календаря
                    'div[class*="calendar"] div:not([class*="disabled"])',
                    'div[class*="Calendar"] div:not([class*="disabled"])',
                    '[role="gridcell"]:not([class*="disabled"])',
                    '[role="button"]:not([disabled])'
                ]
                
                for selector in date_selectors:
                    try:
                        available_dates = self.page.locator(selector)
                        count = await available_dates.count()
                        
                        if count > 0:
                            logger.info(f"✅ Найдено {count} доступных дат через селектор: {selector}")
                            
                            # Выбираем дату с учетом min_hours_ahead
                            from datetime import datetime, timedelta
                            import locale
                            
                            # Устанавливаем русскую локаль для парсинга дат
                            try:
                                locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
                            except:
                                try:
                                    locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
                                except:
                                    pass
                            
                            # НОВАЯ ЛОГИКА: БЫСТРОЕ БРОНИРОВАНИЕ - проверяем ВСЕ даты подряд
                            if not custom_date and not target_coefficient and not selected_dates and not use_max_coefficient:
                                logger.info(f"🚀 РЕЖИМ БЫСТРОГО БРОНИРОВАНИЯ: проверяю ВСЕ даты >= {min_hours_ahead}ч")
                                
                                # Вычисляем минимальную допустимую дату
                                min_date = datetime.now() + timedelta(hours=min_hours_ahead)
                                logger.info(f"📅 Минимальная дата: {min_date.strftime('%d.%m.%Y %H:%M')}")
                                
                                # ПЕРЕБИРАЕМ ВСЕ ДАТЫ И КЛИКАЕМ НА ПЕРВУЮ ПОДХОДЯЩУЮ
                                booked = False
                                for i in range(count):
                                    date_element = available_dates.nth(i)
                                    
                                    try:
                                        date_text = await date_element.text_content()
                                        if not date_text:
                                            continue
                                        
                                        # Парсим дату
                                        import re
                                        clean_date_text = re.sub(r'(Приёмка|Бесплатно|Логистика|Хранение|Отмена|\d+%)', '', date_text)
                                        date_match = re.search(r'(\d{1,2})\s+(\w+)', clean_date_text)
                                        
                                        if not date_match:
                                            continue
                                        
                                        day = int(date_match.group(1))
                                        month_name = date_match.group(2)
                                        
                                        months = {
                                            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                                            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                                            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
                                        }
                                        
                                        if month_name not in months:
                                            continue
                                        
                                        month = months[month_name]
                                        current_year = datetime.now().year
                                        parsed_date = datetime(current_year, month, day)
                                        
                                        # Если дата в прошлом, берем следующий год
                                        if parsed_date < datetime.now():
                                            parsed_date = datetime(current_year + 1, month, day)
                                        
                                        # ПРОВЕРЯЕМ ЧТО ДАТА >= min_hours_ahead
                                        if parsed_date < min_date:
                                            logger.debug(f"⏭️ Дата {parsed_date.strftime('%d.%m.%Y')} слишком близко, пропускаю")
                                            continue
                                        
                                        logger.info(f"✅ Найдена подходящая дата: {parsed_date.strftime('%d.%m.%Y')} (>= {min_date.strftime('%d.%m.%Y %H:%M')})")
                                        
                                        # СРАЗУ ПРОБУЕМ КЛИКНУТЬ
                                        logger.info(f"🖱️ Навожу мышь на дату: {date_text}")
                                        await date_element.hover(timeout=3000, force=True)
                                        await asyncio.sleep(0.5)
                                        
                                        # Ищем кнопку "Выбрать"
                                        select_selectors = [
                                            'button[data-testid*="choose-date"]',
                                            'button:has-text("Выбрать")',
                                            'button[class*="button__QmJ2ep"]'
                                        ]
                                        
                                        select_button = None
                                        for sel_selector in select_selectors:
                                            try:
                                                select_button = self.page.locator(sel_selector).first
                                                if await select_button.is_visible(timeout=2000):
                                                    break
                                            except:
                                                continue
                                        
                                        if select_button and await select_button.is_visible():
                                            logger.info(f"🎯 Кликаю на кнопку 'Выбрать' для даты {parsed_date.strftime('%d.%m.%Y')}")
                                            await select_button.click()
                                            await asyncio.sleep(2)
                                            
                                            # Ищем кнопку подтверждения
                                            confirm_selectors = [
                                                'button:has-text("Подтвердить")',
                                                'button:has-text("Забронировать")',
                                                'button[class*="primary"]'
                                            ]
                                            
                                            for conf_selector in confirm_selectors:
                                                try:
                                                    confirm_btn = self.page.locator(conf_selector).first
                                                    if await confirm_btn.is_visible(timeout=2000):
                                                        await confirm_btn.click()
                                                        logger.info(f"✅ Подтверждение нажато для даты {parsed_date.strftime('%d.%m.%Y')}")
                                                        booked = True
                                                        break
                                                except:
                                                    continue
                                            
                                            if booked:
                                                result["success"] = True
                                                result["booked_date"] = parsed_date.strftime('%d.%m.%Y')
                                                result["message"] = f"✅ Поставка забронирована на {parsed_date.strftime('%d.%m.%Y')}"
                                                logger.info(f"🎉 УСПЕШНО ЗАБРОНИРОВАНО на {parsed_date.strftime('%d.%m.%Y')}")
                                                return result
                                            
                                    except Exception as e:
                                        logger.debug(f"Ошибка обработки даты {i}: {e}")
                                        continue
                                
                                if not booked:
                                    result["message"] = f"❌ Не найдено доступных дат >= {min_hours_ahead}ч ({min_hours_ahead/24:.1f} дней)"
                                    logger.warning(result["message"])
                                    return result
                            
                            # ОПРЕДЕЛЯЕМ ЦЕЛЕВУЮ ДАТУ (для других режимов)
                            if selected_dates and target_coefficient is not None:
                                # Новая логика: ищем подходящую дату из списка выбранных пользователем
                                target_date = await self._find_suitable_date_from_list(selected_dates, target_coefficient, available_dates)
                                if not target_date:
                                    result["message"] = f"❌ Среди выбранных дат нет подходящих с коэффициентом <= {target_coefficient}"
                                    return result
                                logger.info(f"🎯 Выбрана дата из списка пользователя: {target_date}")
                            elif custom_date:
                                # Парсим кастомную дату
                                target_date = self._parse_custom_date(custom_date)
                                logger.info(f"📅 Используем кастомную дату: {custom_date} -> {target_date}")
                                
                                # Если указан коэффициент, проверяем его для выбранной даты
                                if target_coefficient is not None:
                                    actual_coefficient = await self._find_coefficient_for_specific_date(target_date, available_dates)
                                    if actual_coefficient is not None:
                                        if actual_coefficient > target_coefficient:
                                            logger.warning(f"❌ Коэффициент для даты {target_date.strftime('%d.%m.%Y')} слишком высокий: {actual_coefficient} > {target_coefficient}")
                                            result["message"] = f"❌ Коэффициент для выбранной даты ({actual_coefficient}) превышает допустимый ({target_coefficient})"
                                            return result
                                        else:
                                            logger.info(f"✅ Коэффициент для даты {target_date.strftime('%d.%m.%Y')} подходит: {actual_coefficient} <= {target_coefficient}")
                                    else:
                                        logger.warning(f"⚠️ Не удалось найти коэффициент для даты {target_date.strftime('%d.%m.%Y')}")
                            elif target_coefficient is not None:
                                # Ищем дату с коэффициентом <= указанного
                                target_date = await self._find_coefficient_date(target_coefficient, available_dates)
                                if not target_date:
                                    # Если не нашли с нужным коэффициентом, используем дату через 3 дня
                                    target_date = datetime.now() + timedelta(days=3)
                                    logger.warning(f"⚠️ Дата с коэффициентом <= {target_coefficient} не найдена, используем стандартную: {target_date}")
                                else:
                                    logger.info(f"📊 Найдена дата с подходящим коэффициентом: {target_date}")
                            elif use_max_coefficient:
                                # Найдем дату с максимальным коэффициентом (НЕ БЛИЖЕ чем min_hours_ahead)
                                target_date = await self._find_max_coefficient_date_with_min_hours(available_dates, min_hours_ahead)
                                if not target_date:
                                    # Если не нашли, используем минимальную допустимую дату
                                    target_date = datetime.now() + timedelta(hours=min_hours_ahead)
                                logger.info(f"📊 Используем дату с максимальным коэффициентом (не ближе {min_hours_ahead}ч): {target_date}")
                            else:
                                # По умолчанию: ПЕРВАЯ активная дата НЕ БЛИЖЕ чем min_hours_ahead
                                target_date = await self._find_first_available_date_with_min_hours(available_dates, min_hours_ahead)
                                if not target_date:
                                    # Если не нашли активную дату, используем минимальную допустимую
                                    target_date = datetime.now() + timedelta(hours=min_hours_ahead)
                                logger.info(f"🎯 Используем ПЕРВУЮ доступную дату (не ближе {min_hours_ahead}ч = {min_hours_ahead/24:.1f} дней): {target_date}")
                            
                            target_day = target_date.day
                            target_month = target_date.month
                            target_year = target_date.year
                            
                            logger.info(f"🎯 ИЩЕМ ТОЧНУЮ ДАТУ: {target_date.strftime('%d %B %Y (%a)')} - день {target_day}, месяц {target_month}")
                            
                            # Ищем ИМЕННО эту дату, а не первую попавшуюся!
                            target_date_found = False
                            for i in range(count):
                                date_element = available_dates.nth(i)
                                
                                # Пробуем получить дату из атрибутов
                                date_text = None
                                for attr in ['data-date', 'data-value', 'aria-label', 'title']:
                                    try:
                                        date_text = await date_element.get_attribute(attr)
                                        if date_text:
                                            break
                                    except:
                                        continue
                                
                                # Если не нашли в атрибутах, берем текст
                                if not date_text:
                                    date_text = await date_element.text_content()
                                
                                logger.info(f"📅 Проверяю дату: {date_text}")
                                
                                # КРИТИЧНО: парсим дату и проверяем что она НЕ СЕГОДНЯ!
                                if date_text:
                                    try:
                                        import re
                                        # Очищаем текст от лишнего мусора (логистика, хранение и т.д.)
                                        clean_date_text = re.sub(r'(Приёмка|Бесплатно|Логистика|Хранение|Отмена|\d+%)', '', date_text)
                                        
                                        # Ищем паттерн "число месяц"
                                        date_match = re.search(r'(\d{1,2})\s+(\w+)', clean_date_text)
                                        if date_match:
                                            day = int(date_match.group(1))
                                            month_name = date_match.group(2)
                                            
                                            # Словарь месяцев
                                            months = {
                                                'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                                                'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                                                'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
                                            }
                                            
                                            if month_name in months:
                                                month = months[month_name]
                                                current_year = datetime.now().year
                                                
                                                # Создаем дату
                                                parsed_date = datetime(current_year, month, day)
                                                
                                                # Если дата в прошлом, берем следующий год
                                                if parsed_date < datetime.now():
                                                    parsed_date = datetime(current_year + 1, month, day)
                                                
                                                logger.info(f"🔍 Распарсенная дата: {parsed_date}, целевая дата: {target_date}")
                                                
                                                # БЛЯДСКАЯ ТОЧНАЯ ПРОВЕРКА! НЕ "ПОДХОДЯЩАЯ", А "ТОЧНАЯ"!
                                                if parsed_date.day == target_day and parsed_date.month == target_month:
                                                    logger.info(f"🎯 ЭТО ОНА! ТОЧНАЯ ДАТА: {clean_date_text} = {target_day}.{target_month}")
                                                    target_date_found = True
                                                else:
                                                    logger.info(f"❌ Дата {clean_date_text} ({parsed_date.day}.{parsed_date.month}) != нужной ({target_day}.{target_month})")
                                                    continue
                                    except Exception as e:
                                        logger.warning(f"⚠️ Ошибка парсинга даты '{date_text}': {e}")
                                        # НЕ принимаем дату если не можем распарсить!
                                        continue
                                
                                if not target_date_found:
                                    logger.info(f"❌ Дата {date_text} не та что нужна, ищу дальше...")
                                    continue
                                
                                # КРИТИЧЕСКИ ВАЖНО: кнопка появляется только при hover на дату!
                                logger.info(f"🖱️ Навожу мышь на дату: {date_text}")
                                try:
                                    await date_element.hover(timeout=3000, force=True)
                                    await asyncio.sleep(0.5)  # Увеличиваем время ожидания появления кнопки
                                except Exception as hover_error:
                                    logger.warning(f"⚠️ Ошибка наведения на дату {date_text}: {hover_error}")
                                    continue  # Пропускаем эту дату
                                
                                # Ждем появления кнопки "Выбрать" с несколькими попытками
                                select_button = None
                                select_selectors = [
                                    # ТОЧНЫЕ селекторы из обновленного HTML кода
                                    'button[class*="button__QmJ2ep+bvz"][class*="s_vFIVMtH331"][data-testid*="calendar-cell-choose-date-1-2-button-secondary"]',
                                    'button[data-testid="calendar-cell-choose-date-1-2-button-secondary"]',
                                    'button[class*="button__QmJ2ep+bvz"]:has-text("Выбрать")',
                                    'button[class*="s_vFIVMtH331"]:has-text("Выбрать")',
                                    'span[class*="caption__hRApPYLnnH"][data-testid="text"]:has-text("Выбрать")',
                                    # Общие селекторы
                                    '[data-testid*="calendar-cell-choose-date"]',
                                    'button[data-testid*="choose-date"]', 
                                    'button:has-text("Выбрать")',
                                    'button:has-text("выбрать")',
                                    # Селекторы по классам из HTML
                                    'button[class*="button__QmJ2ep"]',
                                    'button[class*="s_vFIVMtH331"]',
                                    # Fallback селекторы
                                    'button:has-text("common-translates.choose")',
                                    'div[class*="calendar"] button:visible',
                                    'div[class*="Calendar"] button:visible',
                                    '[role="gridcell"] button:visible',
                                    '[data-testid*="select"]',
                                    'button[type="button"]:visible'
                                ]
                                
                                # Ждем появления кнопки с множественными попытками hover
                                for attempt in range(6):  # Больше попыток
                                    # Повторяем hover каждую попытку - кнопка может исчезнуть
                                    try:
                                        await date_element.hover(timeout=2000, force=True)
                                        await asyncio.sleep(0.5)  # Время для появления кнопки
                                    except Exception as hover_error:
                                        logger.warning(f"⚠️ Ошибка повторного наведения на попытке {attempt + 1}: {hover_error}")
                                        continue
                                    
                                    # Проверяем все селекторы
                                    for sel in select_selectors:
                                        try:
                                            buttons = self.page.locator(sel)
                                            button_count = await buttons.count()
                                            
                                            for i in range(button_count):
                                                btn = buttons.nth(i)
                                                if await btn.is_visible():
                                                    # Дополнительная проверка текста
                                                    try:
                                                        btn_text = await btn.text_content()
                                                        if btn_text and any(word in btn_text.lower() for word in 
                                                                          ['выбрать', 'choose', 'common-translates.choose']):
                                                            select_button = btn
                                                            logger.info(f"✅ Кнопка найдена через {attempt + 1} попытку: {sel}, текст: '{btn_text}'")
                                                            break
                                                    except:
                                                        # Если не можем получить текст, берем кнопку
                                                        select_button = btn
                                                        logger.info(f"✅ Кнопка найдена через {attempt + 1} попытку: {sel}")
                                                        break
                                        except Exception as e:
                                            continue
                                    
                                    if select_button:
                                        break
                                        
                                    logger.info(f"⏳ Попытка {attempt + 1}/6: кнопка не найдена, повторяю hover...")
                                
                                # Если стандартные селекторы не сработали, используем DOM анализ
                                if not select_button:
                                    logger.info("🔍 Анализирую DOM структуру после hover...")
                                    
                                    # Еще один hover для активации
                                    try:
                                        await date_element.hover(timeout=2000, force=True)
                                        await asyncio.sleep(0.3)  # УМЕНЬШИЛ С 1.0 ДО 0.3 СЕКУНДЫ!
                                    except Exception as hover_error:
                                        logger.warning(f"⚠️ Ошибка финального наведения: {hover_error}")
                                        # Продолжаем без наведения
                                    
                                    # Ищем все кнопки, которые появились после hover
                                    dom_analysis = await self.page.evaluate("""
                                        () => {
                                            const results = [];
                                            
                                            // Ищем все кнопки на странице
                                            const allButtons = document.querySelectorAll('button, [role="button"]');
                                            
                                            allButtons.forEach((btn, index) => {
                                                const rect = btn.getBoundingClientRect();
                                                const isVisible = rect.width > 0 && rect.height > 0 && 
                                                                btn.offsetParent !== null;
                                                
                                                if (isVisible) {
                                                    const text = btn.textContent || btn.innerText || '';
                                                    const classes = btn.className || '';
                                                    const testId = btn.getAttribute('data-testid') || '';
                                                    
                                                    // Проверяем если это кнопка "Выбрать"
                                                    if (text.includes('Выбрать') || 
                                                        text.includes('common-translates.choose') ||
                                                        text.includes('choose') ||
                                                        testId.includes('choose') ||
                                                        testId.includes('select')) {
                                                        
                                                        results.push({
                                                            index: index,
                                                            text: text,
                                                            classes: classes,
                                                            testId: testId,
                                                            html: btn.outerHTML.substring(0, 200),
                                                            position: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                                                        });
                                                    }
                                                }
                                            });
                                            
                                            return results;
                                        }
                                    """)
                                    
                                    if dom_analysis:
                                        logger.info(f"🎯 DOM анализ нашел {len(dom_analysis)} подходящих кнопок:")
                                        for i, btn_info in enumerate(dom_analysis):
                                            logger.info(f"  Кнопка {i+1}: '{btn_info.get('text', '')}' (testId: {btn_info.get('testId', '')})")
                                        
                                        # Берем первую найденную кнопку
                                        first_btn = dom_analysis[0]
                                        if 'common-translates.choose' in first_btn.get('text', '') or first_btn.get('testId', ''):
                                            select_button = self.page.locator('button').nth(first_btn['index'])
                                            logger.info("✅ Выбрана кнопка через DOM анализ")
                                    
                                    # Альтернативный поиск по координатам мыши
                                    try:
                                        # Получаем координаты мыши
                                        mouse_pos = await self.page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
                                        
                                        # Ищем элемент под курсором мыши
                                        element_at_mouse = await self.page.evaluate(f"""
                                            () => {{
                                                const element = document.elementFromPoint({mouse_pos.get('x', 0)}, {mouse_pos.get('y', 0)});
                                                if (element && (element.tagName === 'BUTTON' || element.textContent?.includes('Выбрать') || element.textContent?.includes('common-translates.choose'))) {{
                                                    return element.outerHTML;
                                                }}
                                                return null;
                                            }}
                                        """)
                                        
                                        if element_at_mouse:
                                            logger.info("✅ Найдена кнопка под курсором мыши")
                                            select_button = self.page.locator('button').filter(has_text="Выбрать").first
                                            break
                                    except:
                                        continue
                                
                                # Если кнопка не найдена, пробуем найти по другим признакам
                                if not select_button or await select_button.count() == 0:
                                    logger.info("🔍 Ищу кнопку 'Выбрать' по другим признакам...")
                                    
                                    # Ищем в popup окне
                                    try:
                                        popup_buttons = self.page.locator('#portal button, [id*="Portal"] button, [class*="modal"] button')
                                        button_count = await popup_buttons.count()
                                        logger.info(f"🔍 Найдено {button_count} кнопок в popup")
                                        
                                        for i in range(button_count):
                                            btn = popup_buttons.nth(i)
                                            try:
                                                btn_text = await btn.text_content()
                                                if btn_text and ("выбрать" in btn_text.lower() or "выбор" in btn_text.lower() or
                                                                "common-translates.choose" in btn_text or "common-translates.modalCancelButton" in btn_text):
                                                    select_button = btn
                                                    logger.info(f"✅ Найдена кнопка по тексту: {btn_text}")
                                                    break
                                            except:
                                                continue
                                        
                                        # Если не найдено, ищем по локализационным ключам
                                        if not select_button or await select_button.count() == 0:
                                            logger.info("🔍 Ищу по локализационным ключам...")
                                            for key in ["common-translates.choose", "common-translates.modalCancelButton"]:
                                                try:
                                                    key_button = self.page.locator(f'button:has-text("{key}")')
                                                    if await key_button.count() > 0:
                                                        select_button = key_button.first
                                                        logger.info(f"✅ Найдена кнопка по ключу: {key}")
                                                        break
                                                except:
                                                    continue
                                    except Exception as e:
                                        logger.warning(f"⚠️ Ошибка fallback поиска: {e}")
                                    
                                    # Ищем любые кнопки в popup окне
                                    popup_buttons = self.page.locator('[id*="Portal-CalendarPlanModal"] button, [class*="Portal-CalendarPlanModal"] button')
                                    button_count = await popup_buttons.count()
                                    
                                    for i in range(button_count):
                                        try:
                                            btn = popup_buttons.nth(i)
                                            btn_text = await btn.text_content()
                                            if btn_text and ("выбрать" in btn_text.lower() or "выбор" in btn_text.lower() or 
                                                           "common-translates.choose" in btn_text or "common-translates.modalCancelButton" in btn_text):
                                                select_button = btn
                                                logger.info(f"✅ Найдена кнопка по тексту: {btn_text}")
                                                break
                                        except:
                                            continue
                                
                                # Если кнопка "Выбрать" появилась - кликаем через JavaScript
                                if select_button and await select_button.count() > 0:
                                    try:
                                        # ОСТОРОЖНО: убираем ТОЛЬКО мешающие элементы, НЕ ЛОМАЯ модальное окно
                                        await self.page.evaluate("""
                                            // НЕ ТРОГАЕМ calendar-header-container - он нужен для работы модального окна!
                                            
                                            // Убираем только внешние overlay элементы (НЕ внутри модального окна)
                                            const overlayElements = document.querySelectorAll('[data-name="Overlay"]:not([id*="Portal"] [data-name="Overlay"])');
                                            overlayElements.forEach(overlay => {
                                                const rect = overlay.getBoundingClientRect();
                                                // Убираем только большие оверлеи (полноэкранные)
                                                if (rect.width > window.innerWidth * 0.8 && rect.height > window.innerHeight * 0.8) {
                                                    overlay.style.pointerEvents = 'none';
                                                    overlay.style.zIndex = '-1';
                                                }
                                            });
                                            
                                            // НЕ УБИРАЕМ [role="presentation"] - это часть модального окна!
                                            
                                            // НЕ УБИРАЕМ модальные окна - они нужны для работы!
                                            
                                            // НЕ БЛОКИРУЕМ addEventListener - это убивает модальное окно!
                                        """)
                                        
                                        # Ждем немного
                                        await asyncio.sleep(0.2)
                                        
                                        # МЯГКИЙ клик на кнопку "Выбрать" - НЕ ЛОМАЕМ модальное окно!
                                        try:
                                            # Просто обычный клик - НЕ ИСПОЛЬЗУЕМ агрессивный JavaScript!
                                            await select_button.click()
                                            logger.info("✅ Кликнул на 'Выбрать' обычным способом")
                                        except Exception as click_error:
                                            logger.warning(f"⚠️ Обычный клик не сработал: {click_error}")
                                            # Только если обычный клик не работает - используем мягкий JavaScript
                                            await select_button.evaluate("""
                                                button => {
                                                    // НЕ КЛОНИРУЕМ кнопку - это может сломать модальное окно!
                                                    // Просто кликаем аккуратно
                                                    const event = new MouseEvent('click', {
                                                        view: window,
                                                        bubbles: true,
                                                        cancelable: true
                                                    });
                                                    button.dispatchEvent(event);
                                                    button.click();
                                                }
                                            """)
                                            logger.info("✅ Кликнул на 'Выбрать' через мягкий JavaScript")
                                    except Exception as click_error:
                                        logger.warning(f"⚠️ Ошибка JavaScript клика на 'Выбрать': {click_error}")
                                        # Fallback на обычный клик
                                        try:
                                            await select_button.click()
                                            logger.info("✅ Кликнул на 'Выбрать' через Playwright")
                                        except Exception as click_error2:
                                            logger.warning(f"⚠️ Ошибка клика на 'Выбрать': {click_error2}")
                                            # Пробуем кликнуть на дату
                                            await date_element.evaluate("element => element.click()")
                                            logger.info("✅ Кликнул на дату вместо 'Выбрать'")
                                else:
                                    # Иначе кликаем на саму дату
                                    await date_element.click()
                                    logger.info("✅ Кликнул на дату")
                                
                                # КРИТИЧНО: Проверяем, что модальное окно не закрылось!
                                await asyncio.sleep(1)
                                popup_still_open = await self.page.locator('[class*="calendar"], [id*="Portal"]').count()
                                if popup_still_open == 0:
                                    logger.error("❌ ДЕРЬМО! Модальное окно закрылось после клика!")
                                    if attempt < max_attempts:
                                        logger.info("🔄 Перезагружаю страницу и пробую снова...")
                                        await self.page.reload(wait_until='domcontentloaded')
                                        await asyncio.sleep(3)
                                        continue
                                    else:
                                        result["message"] = "❌ Модальное окно закрывается после клика - нужно исправить код"
                                        return result
                                else:
                                    logger.info("✅ Модальное окно все еще открыто")
                                
                                date_found = True
                                selected_date = date_text
                                logger.info(f"🎯 ТОЧНАЯ ДАТА НАЙДЕНА И ВЫБРАНА! Выхожу из всех циклов.")
                                await asyncio.sleep(0.5)  # Ждем активации кнопки "Забронировать"
                                
                                # Ищем кнопку "Забронировать" которая должна появиться после выбора даты
                                final_book_button = None
                                final_book_selectors = [
                                    'button:has-text("Забронировать")',
                                    'button:has-text("Забронировать поставку")',
                                    'button:has-text("Подтвердить")',
                                    'button:has-text("Готово")',
                                    'button[class*="book"]',
                                    'button[class*="confirm"]'
                                ]
                                
                                for sel in final_book_selectors:
                                    try:
                                        final_book_button = self.page.locator(sel).first
                                        if await final_book_button.count() > 0 and await final_book_button.is_visible():
                                            logger.info(f"✅ Найдена финальная кнопка бронирования: {sel}")
                                            break
                                    except:
                                        continue
                                
                                if final_book_button and await final_book_button.count() > 0:
                                    try:
                                        await final_book_button.click()
                                        logger.info("✅ Кликнул на финальную кнопку бронирования")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Ошибка клика на финальную кнопку: {e}")
                                
                                break
                            
                            if date_found:
                                break
                    except Exception as e:
                        logger.debug(f"Ошибка с селектором {selector}: {e}")
                        continue
                
                if not date_found:
                    logger.error("❌ Не найдено доступных дат для бронирования")
                    await self.take_screenshot(f"no_dates_attempt_{attempt}.png")
                    
                    if attempt < max_attempts:
                        # Закрываем модальное окно и пробуем снова
                        try:
                            close_button = self.page.locator('button[class*="close"], [aria-label*="close"], .modal-close').first
                            if await close_button.count() > 0:
                                await close_button.click()
                                await asyncio.sleep(2)
                        except:
                            pass
                        continue
                    else:
                        result["message"] = "❌ Нет доступных дат для бронирования"
                        return result
                
                # Шаг 5: Ждем появления кнопки "Запланировать" после клика на "Выбрать"
                logger.info("⏳ ДОЛГО жду появления кнопки 'Запланировать' после выбора даты...")
                
                # БЛЯДЬ! ДЕЛАЮ АКТИВНОЕ ОЖИДАНИЕ ПОЯВЛЕНИЯ КНОПКИ!
                confirm_button_appeared = False
                for attempt in range(15):  # 15 попыток по 1 секунде = 15 секунд максимум
                    await asyncio.sleep(1)
                    
                    # Проверяем есть ли кнопка "Запланировать"
                    test_buttons = self.page.locator('button:has-text("Запланировать"), button:has-text("Забронировать"), span:has-text("Запланировать")')
                    button_count = await test_buttons.count()
                    
                    if button_count > 0:
                        confirm_button_appeared = True
                        logger.info(f"🎯 НАШЕЛ КНОПКУ! Попытка {attempt + 1}, найдено кнопок: {button_count}")
                        break
                    else:
                        logger.info(f"⏳ Попытка {attempt + 1}/15 - кнопка еще не появилась...")
                
                if not confirm_button_appeared:
                    logger.warning("⚠️ Кнопка 'Запланировать' так и не появилась за 15 секунд!")
                
                confirm_button = None
                confirm_texts = [
                    "Запланировать",  # Точный текст из HTML
                    "Забронировать",
                    "Подтвердить",
                    "Сохранить",
                    "OK",
                    "Готово"
                ]
                
                # ВАЖНО: ищем кнопку ТОЛЬКО внутри модального окна!
                modal_locators = [
                    '[class*="calendar"]',
                    '[id*="Portal"]', 
                    '[role="dialog"]',
                    '[class*="Modal"]',
                    '[data-testid*="modal"]'
                ]
                
                modal_found = None
                for modal_selector in modal_locators:
                    try:
                        modal_elements = self.page.locator(modal_selector)
                        if await modal_elements.count() > 0:
                            modal_found = modal_elements.first
                            logger.info(f"✅ Найдено модальное окно для поиска кнопки: {modal_selector}")
                            break
                    except:
                        continue
                
                if modal_found:
                    # ДЕБАГ: логируем HTML структуру модального окна
                    try:
                        modal_html = await modal_found.inner_html()
                        logger.info(f"📄 HTML модального окна (первые 500 символов): {modal_html[:500]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось получить HTML модального окна: {e}")
                    
                    # Ищем кнопку ВНУТРИ модального окна
                    for btn_text in confirm_texts:
                        try:
                            # Ищем кнопку ВНУТРИ модального окна
                            button_selector = f'button:has-text("{btn_text}"):not([disabled])'
                            confirm_button = modal_found.locator(button_selector).first
                            
                            if await confirm_button.count() > 0 and await confirm_button.is_visible():
                                logger.info(f"✅ Найдена кнопка подтверждения ВНУТРИ модального окна: {btn_text}")
                                break
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка поиска кнопки {btn_text} в модальном окне: {e}")
                            continue
                else:
                    logger.warning("⚠️ Модальное окно не найдено, ищу кнопку по всей странице...")
                    # Fallback: ищем по всей странице
                    for btn_text in confirm_texts:
                        try:
                            # Проверяем что кнопка активна
                            button_selector = f'button:has-text("{btn_text}"):not([disabled])'
                            confirm_button = self.page.locator(button_selector).first
                            
                            if await confirm_button.count() > 0 and await confirm_button.is_visible():
                                logger.info(f"✅ Найдена активная кнопка подтверждения: {btn_text}")
                                break
                        except:
                            continue
                
                # Если не найдена по тексту, ищем по точному селектору из HTML ВНУТРИ модального окна
                if not confirm_button or await confirm_button.count() == 0:
                    logger.info("🔍 Ищу кнопку 'Запланировать' по точным селекторам ВНУТРИ модального окна...")
                    
                    # ТОЧНЫЕ селекторы из твоего HTML кода
                    confirm_selectors = [
                        'span[class*="caption__0iy-jJu+aV"]:has-text("Запланировать")',  # Точный класс
                        'button:has(span[class*="caption__0iy-jJu+aV"])',  # Кнопка с этим span
                        'span.caption__0iy-jJu+aV',  # Прямой класс
                        'button span:has-text("Запланировать")',  # Любой span с текстом
                        'button:has-text("Запланировать")',  # Кнопка с текстом
                        '[class*="caption__0iy-jJu+aV"]',  # По классу
                    ]
                    
                    # Если есть модальное окно - ищем внутри него
                    search_context = modal_found if modal_found else self.page
                    context_name = "модального окна" if modal_found else "всей страницы"
                    
                    for selector in confirm_selectors:
                        try:
                            button_elements = search_context.locator(selector)
                            button_count = await button_elements.count()
                            
                            if button_count > 0:
                                for i in range(button_count):
                                    btn = button_elements.nth(i)
                                    if await btn.is_visible():
                                        # Проверяем текст
                                        btn_text = await btn.text_content()
                                        if btn_text and "запланировать" in btn_text.lower():
                                            confirm_button = btn
                                            logger.info(f"✅ Найдена кнопка 'Запланировать' по селектору ВНУТРИ {context_name}: {selector}, текст: '{btn_text}'")
                                            break
                            
                            if confirm_button and await confirm_button.count() > 0:
                                break
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка поиска по селектору {selector} внутри {context_name}: {e}")
                            continue

                # ПОСЛЕДНЯЯ ПОПЫТКА: ищем ЛЮБУЮ кнопку в модальном окне
                if not confirm_button or await confirm_button.count() == 0:
                    logger.warning("⚠️ Кнопка не найдена по стандартным селекторам, ищу ЛЮБЫЕ кнопки в модальном окне...")
                    
                    if modal_found:
                        try:
                            # Ищем ВСЕ кнопки в модальном окне
                            all_buttons = modal_found.locator('button')
                            button_count = await all_buttons.count()
                            
                            logger.info(f"🔍 Найдено {button_count} кнопок в модальном окне")
                            
                            for i in range(button_count):
                                btn = all_buttons.nth(i)
                                if await btn.is_visible() and await btn.is_enabled():
                                    # Получаем текст кнопки
                                    btn_text = await btn.text_content()
                                    
                                    # КРИТИЧНО: Если текст кнопки пустой, ищем в дочерних span элементах!
                                    if not btn_text or btn_text.strip() == '':
                                        try:
                                            # Ищем span внутри кнопки
                                            span_elements = btn.locator('span')
                                            span_count = await span_elements.count()
                                            
                                            span_texts = []
                                            for j in range(span_count):
                                                span_text = await span_elements.nth(j).text_content()
                                                if span_text and span_text.strip():
                                                    span_texts.append(span_text.strip())
                                            
                                            btn_text = ' '.join(span_texts) if span_texts else ''
                                            
                                        except Exception as e:
                                            logger.warning(f"⚠️ Ошибка чтения span в кнопке {i}: {e}")
                                    
                                    logger.info(f"🔎 Кнопка {i}: '{btn_text}'")
                                    
                                    # Проверяем по ключевым словам
                                    if btn_text and any(keyword in btn_text.lower() for keyword in 
                                        ["запланировать", "подтвердить", "забронировать", "готово", "ok", "сохранить", "далее"]):
                                        confirm_button = btn
                                        logger.info(f"✅ НАЙДЕНА подходящая кнопка: '{btn_text}'")
                                        break
                        except Exception as e:
                            logger.error(f"❌ Ошибка поиска всех кнопок: {e}")
                
                # ДОПОЛНИТЕЛЬНЫЙ ПОИСК: ищем по data-testid и классам
                if not confirm_button or await confirm_button.count() == 0:
                    logger.warning("⚠️ Ищу по альтернативным селекторам...")
                    
                    alternative_selectors = [
                        # По data-testid
                        '[data-testid*="button"]',
                        '[data-testid*="confirm"]', 
                        '[data-testid*="submit"]',
                        # По классам из твоего HTML
                        '[class*="caption__0iy-jJu+aV"]',
                        '[class*="button__"]',
                        # По типу
                        'button[type="submit"]',
                        'input[type="submit"]',
                        # По роли
                        '[role="button"]'
                    ]
                    
                    search_context = modal_found if modal_found else self.page
                    
                    for selector in alternative_selectors:
                        try:
                            elements = search_context.locator(selector)
                            count = await elements.count()
                            
                            if count > 0:
                                logger.info(f"🔍 Найдено {count} элементов по селектору: {selector}")
                                
                                for i in range(count):
                                    elem = elements.nth(i)
                                    if await elem.is_visible():
                                        elem_text = await elem.text_content()
                                        logger.info(f"🔎 Элемент {i} ({selector}): '{elem_text}'")
                                        
                                        if elem_text and any(keyword in elem_text.lower() for keyword in 
                                            ["запланировать", "подтвердить", "забронировать"]):
                                            confirm_button = elem
                                            logger.info(f"✅ НАЙДЕН элемент через альтернативный селектор: '{elem_text}'")
                                            break
                            
                            if confirm_button and await confirm_button.count() > 0:
                                break
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка поиска по селектору {selector}: {e}")
                            continue
                
                # КРИТИЧНЫЙ ДЕБАГ: если всё ещё не найдена, ищем ПО ВСЕЙ СТРАНИЦЕ
                if not confirm_button or await confirm_button.count() == 0:
                    logger.error("❌ КНОПКА НЕ НАЙДЕНА В МОДАЛЬНОМ ОКНЕ! Ищу по всей странице...")
                    
                    try:
                        # Ищем ВСЕ элементы с текстом "Запланировать" на странице
                        all_page_elements = self.page.locator('*:has-text("Запланировать")')
                        page_count = await all_page_elements.count()
                        
                        logger.info(f"🔍 Найдено {page_count} элементов с текстом 'Запланировать' на всей странице")
                        
                        for i in range(min(page_count, 10)):  # Максимум 10 элементов
                            elem = all_page_elements.nth(i)
                            if await elem.is_visible():
                                elem_text = await elem.text_content()
                                elem_tag = await elem.evaluate('el => el.tagName')
                                elem_class = await elem.get_attribute('class') or ''
                                elem_id = await elem.get_attribute('id') or ''
                                elem_testid = await elem.get_attribute('data-testid') or ''
                                
                                logger.info(f"🔎 Элемент {i}: <{elem_tag}> '{elem_text}' class='{elem_class}' id='{elem_id}' testid='{elem_testid}'")
                                
                                # Если это кнопка или кликабельный элемент
                                if elem_tag.lower() in ['button', 'input'] or 'button' in elem_class.lower():
                                    if "запланировать" in elem_text.lower():
                                        confirm_button = elem
                                        logger.info(f"✅ НАЙДЕНА кнопка ПО ВСЕЙ СТРАНИЦЕ: <{elem_tag}> '{elem_text}'")
                                        break
                        
                        # Также ищем по твоему точному классу по всей странице
                        if not confirm_button or await confirm_button.count() == 0:
                            exact_class_buttons = self.page.locator('span[class*="caption__0iy-jJu+aV"]')
                            exact_count = await exact_class_buttons.count()
                            
                            logger.info(f"🔍 Найдено {exact_count} элементов с точным классом caption__0iy-jJu+aV")
                            
                            for i in range(exact_count):
                                span = exact_class_buttons.nth(i)
                                if await span.is_visible():
                                    span_text = await span.text_content()
                                    logger.info(f"🔎 Span {i}: '{span_text}'")
                                    
                                    if span_text and "запланировать" in span_text.lower():
                                        # Ищем родительскую кнопку
                                        parent_button = span.locator('xpath=ancestor::button[1]')
                                        if await parent_button.count() > 0:
                                            confirm_button = parent_button.first
                                            logger.info(f"✅ НАЙДЕНА кнопка через span с точным классом: '{span_text}'")
                                            break
                    
                    except Exception as e:
                        logger.error(f"❌ Ошибка поиска по всей странице: {e}")
                
                if not confirm_button or await confirm_button.count() == 0:
                    logger.error("❌ Кнопка подтверждения не найдена НИГДЕ на странице!")
                    await self.take_screenshot(f"no_confirm_button_attempt_{attempt}.png")
                    
                    if attempt < max_attempts:
                        continue
                    else:
                        result["message"] = "❌ Кнопка подтверждения бронирования не найдена"
                        return result
                
                # МЯГКИЙ клик на кнопку подтверждения - НЕ ЛОМАЕМ интерфейс!
                try:
                    # НЕ УБИРАЕМ элементы модального окна - они нужны для его работы!
                    
                    # Просто обычный клик
                    await confirm_button.click()
                    logger.info("✅ Нажал кнопку подтверждения обычным способом")
                    
                    # БОЛЬШЕ ВРЕМЕНИ ПОСЛЕ КЛИКА ДЛЯ ОБРАБОТКИ НА СЕРВЕРЕ WB!
                    logger.info("⏳ Жду ответа от сервера WB после клика...")
                    await asyncio.sleep(8)  # ДОБАВЛЯЮ 8 СЕКУНД ПОСЛЕ КЛИКА!
                
                except Exception as click_error:
                    logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при бронировании: {click_error}")
                    await self.take_screenshot(f"booking_error_{supply_id}.png")
                    if attempt < max_attempts:
                        continue
                    else:
                        # Очищаем HTML теги из ошибки
                        import html
                        clean_error = html.escape(str(click_error))
                        result["message"] = f"❌ Ошибка клика на кнопку подтверждения: {clean_error}"
                        return result
                
                # КРИТИЧНО: ЖДЕМ ОТВЕТА ОТ WB О РЕЗУЛЬТАТЕ БРОНИРОВАНИЯ!
                logger.info("⏳ Жду ответа от WB о результате бронирования...")
                await asyncio.sleep(3)  # Базовое ожидание для реакции сервера
                
                # ПРОВЕРЯЕМ РЕЗУЛЬТАТ БРОНИРОВАНИЯ
                booking_result = await self._check_booking_success()
                
                if booking_result["success"]:
                    logger.info(f"🎉 БРОНИРОВАНИЕ УСПЕШНО! {booking_result['message']}")
                    result["success"] = True
                    result["message"] = booking_result["message"]
                    
                    # КРИТИЧНО! ПОСЛЕ БРОНИ WB МЕНЯЕТ ID ПОСТАВКИ!
                    # Ищем новый ID в заголовке страницы
                    new_supply_id = await self._find_new_supply_id()
                    if new_supply_id:
                        logger.info(f"🆔 Найден новый ID поставки после брони: {new_supply_id}")
                        
                        # ДОБАВЛЯЕМ ДЕТАЛИ БРОНИРОВАНИЯ С НОВЫМ ID
                        booking_details = await self._get_booking_details(new_supply_id)
                        if booking_details:
                            result.update(booking_details)
                            # Добавляем новый ID в результат
                            result["new_supply_id"] = new_supply_id
                    else:
                        logger.warning(f"⚠️ Не найден новый ID поставки, используем старый: {supply_id}")
                        # FALLBACK: используем старый ID
                        booking_details = await self._get_booking_details(supply_id)
                        if booking_details:
                            result.update(booking_details)
                    
                    return result
                elif booking_result["retry"]:
                    logger.warning(f"⚠️ Нужна повторная попытка: {booking_result['message']}")
                    if attempt < max_attempts:
                        await asyncio.sleep(2)  # Пауза между попытками
                        continue
                    else:
                        result["message"] = f"❌ Превышено максимальное количество попыток: {booking_result['message']}"
                        return result
                else:
                    logger.error(f"❌ БРОНИРОВАНИЕ НЕУДАЧНО: {booking_result['message']}")
                    result["message"] = booking_result["message"]
                    return result
                
                # Шаг 6: Проверяем результат бронирования
                success = False
                error_message = None
                
                # Проверяем уведомления об успехе
                success_selectors = [
                    'text=/успешно забронирована/i',
                    'text=/бронирование выполнено/i',
                    'text=/поставка забронирована/i',
                    'text=/successfully booked/i',
                    '[class*="success"]',
                    '[class*="notification"][class*="success"]',
                    '.toast-success',
                    '[role="alert"][class*="success"]'
                ]
                
                for selector in success_selectors:
                    try:
                        success_element = self.page.locator(selector).first
                        if await success_element.count() > 0:
                            success = True
                            logger.info(f"✅ Найдено уведомление об успехе: {selector}")
                            break
                    except:
                        continue
                
                # Проверяем ошибки
                if not success:
                    error_selectors = [
                        '[class*="error"]',
                        '[class*="alert"][class*="danger"]',
                        '.toast-error',
                        '[role="alert"][class*="error"]',
                        'text=/ошибка/i',
                        'text=/не удалось/i',
                        'text=/failed/i'
                    ]
                    
                    for selector in error_selectors:
                        try:
                            error_element = self.page.locator(selector).first
                            if await error_element.count() > 0:
                                error_message = await error_element.text_content()
                                logger.error(f"❌ Найдена ошибка: {error_message}")
                                break
                        except:
                            continue
                
                if success:
                    result["success"] = True
                    result["message"] = f"✅ Поставка {supply_id} успешно забронирована на {selected_date}!"
                    result["booked_date"] = selected_date
                    logger.info(result["message"])
                    
                    # Делаем скриншот успешного бронирования
                    await self.take_screenshot(f"booking_success_{supply_id}.png")
                    return result
                    
                elif error_message:
                    logger.warning(f"⚠️ Попытка #{attempt}: WB выдал ошибку: {error_message}")
                    
                    if attempt < max_attempts:
                        result["message"] = f"Попытка бронирования #{attempt} не удалась, WB выдал ошибку. Пробую еще раз..."
                        await asyncio.sleep(3)
                        continue
                    else:
                        # Очищаем HTML теги из ошибки
                        import html
                        clean_error = html.escape(str(error_message)) if error_message else "неизвестная ошибка"
                        result["message"] = f"❌ Бронирование не удалось после {max_attempts} попыток. Последняя ошибка: {clean_error}"
                        return result
                else:
                    # Не нашли ни успеха, ни ошибки - проверяем по изменению страницы
                    current_url = self.page.url
                    if "success" in current_url or "confirmed" in current_url:
                        result["success"] = True
                        result["message"] = f"✅ Поставка {supply_id} забронирована (определено по URL)!"
                        result["booked_date"] = selected_date
                        return result
                    
                    if attempt < max_attempts:
                        logger.warning(f"⚠️ Попытка #{attempt}: результат неясен, пробую еще раз")
                        await asyncio.sleep(3)
                        continue
            
            # Если дошли сюда - все попытки исчерпаны
            result["message"] = f"❌ Не удалось забронировать поставку после {max_attempts} попыток"
            return result
            
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при бронировании: {e}")
            # Очищаем HTML теги из ошибки для безопасной передачи в Telegram
            import html
            clean_error = html.escape(str(e))
            result["message"] = f"❌ Ошибка: {clean_error}"
            
            # Делаем скриншот для отладки
            try:
                await self.take_screenshot(f"booking_error_{supply_id}.png")
            except:
                pass
            
            return result

    async def navigate_to_supplies_page(self) -> bool:
        """Переходит на страницу управления поставками."""
        try:
            supplies_url = "https://seller.wildberries.ru/supplies-management/all-supplies"
            logger.info(f"🔗 Перехожу на страницу поставок: {supplies_url}")
            
            response = await self.page.goto(supplies_url, wait_until="networkidle", timeout=15000)
            
            if response and response.status == 200:
                logger.info("✅ Успешно перешел на страницу поставок")
                return True
            else:
                logger.error(f"❌ Ошибка перехода на страницу поставок: {response.status if response else 'No response'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка перехода на страницу поставок: {e}")
            return False

    async def book_supply(self, supply_id: str, preorder_id: str, date_from: str, date_to: str) -> bool:
        """Бронирует поставку по ID на указанные даты."""
        try:
            logger.info(f"🎯 Начинаю бронирование поставки {supply_id} (заказ {preorder_id})")
            
            if not self.page:
                logger.error("❌ Страница не инициализирована")
                return False
            
            # Проверяем авторизацию - если не авторизован, сообщаем об ошибке
            if not await self.check_if_logged_in():
                logger.error("❌ Пользователь не авторизован! Сначала выполните вход в систему.")
                return False
            
            # Если уже на странице поставок - отлично, иначе переходим
            current_url = self.page.url
            if "supplies-management" not in current_url:
                logger.info("📍 Перехожу на страницу поставок...")
                await self.navigate_to_supplies_page()
                await asyncio.sleep(2)
            
            # Ищем поставку по preorderID (так как для статуса 1 supplyID = null)
            logger.info(f"🔍 Ищу заказ {preorder_id} на странице...")
            
            # Ждем загрузки таблицы поставок
            try:
                await self.page.wait_for_selector('table', timeout=10000)
                logger.info("✅ Таблица поставок загружена")
            except:
                logger.warning("⚠️ Таблица поставок не найдена, продолжаю...")
            
            # Ищем строку с нашим заказом
            supply_row = None
            try:
                # Ищем по тексту preorderID
                supply_row = self.page.locator(f'tr:has-text("{preorder_id}")').first
                if await supply_row.count() > 0:
                    logger.info(f"✅ Найдена строка с заказом {preorder_id}")
                else:
                    # Пробуем найти по supply_id если есть
                    if supply_id and supply_id != preorder_id:
                        supply_row = self.page.locator(f'tr:has-text("{supply_id}")').first
                        if await supply_row.count() > 0:
                            logger.info(f"✅ Найдена строка с поставкой {supply_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка поиска поставки: {e}")
                return False
            
            if not supply_row or await supply_row.count() == 0:
                logger.error(f"❌ Поставка {supply_id} не найдена на странице")
                return False
            
            # Кликаем на строку поставки для открытия деталей
            await supply_row.click()
            await asyncio.sleep(2)
            
            # Ищем кнопку "Запланировать" или "Изменить план"
            book_button = None
            button_selectors = [
                'button:has-text("Запланировать")',
                'button:has-text("Изменить план")', 
                'button:has-text("Планировать")',
                '[data-testid="plan-button"]',
                '.plan-button',
                'button[class*="plan"]'
            ]
            
            for selector in button_selectors:
                try:
                    book_button = self.page.locator(selector).first
                    if await book_button.count() > 0:
                        logger.info(f"✅ Найдена кнопка планирования: {selector}")
                        break
                except:
                    continue
            
            if not book_button or await book_button.count() == 0:
                logger.error("❌ Кнопка планирования не найдена")
                return False
            
            # Кликаем кнопку планирования
            await book_button.click()
            await asyncio.sleep(3)
            
            # Ждем появления календаря или модального окна
            try:
                await self.page.wait_for_selector('[class*="calendar"], [class*="date-picker"], .modal', timeout=10000)
                logger.info("✅ Календарь планирования открыт")
            except:
                logger.warning("⚠️ Календарь не найден, продолжаю...")
            
            # Выбираем даты (упрощенная логика - выбираем первый доступный слот)
            date_selectors = [
                f'[data-date="{date_from}"]',
                f'[data-date*="{date_from[:7]}"]',  # По месяцу
                '.available-slot',
                '[class*="available"]',
                'button:not([disabled])'
            ]
            
            date_selected = False
            for selector in date_selectors:
                try:
                    date_element = self.page.locator(selector).first
                    if await date_element.count() > 0:
                        await date_element.click()
                        logger.info(f"✅ Выбрана дата через селектор: {selector}")
                        date_selected = True
                        await asyncio.sleep(1)
                        break
                except:
                    continue
            
            if not date_selected:
                logger.warning("⚠️ Не удалось выбрать конкретную дату, пробую подтвердить...")
            
            # Ищем кнопку подтверждения
            confirm_button = None
            confirm_selectors = [
                'button:has-text("Подтвердить")',
                'button:has-text("Сохранить")',
                'button:has-text("Забронировать")',
                'button:has-text("Запланировать")',
                '[data-testid="confirm-button"]',
                '.confirm-button',
                'button[type="submit"]'
            ]
            
            for selector in confirm_selectors:
                try:
                    confirm_button = self.page.locator(selector).first
                    if await confirm_button.count() > 0:
                        logger.info(f"✅ Найдена кнопка подтверждения: {selector}")
                        break
                except:
                    continue
            
            if confirm_button and await confirm_button.count() > 0:
                await confirm_button.click()
                await asyncio.sleep(3)
                logger.info("✅ Кнопка подтверждения нажата")
            else:
                logger.warning("⚠️ Кнопка подтверждения не найдена")
            
            # Проверяем успешность бронирования
            success_indicators = [
                'text="Поставка запланирована"',
                'text="Успешно"',
                '[class*="success"]',
                '.notification-success'
            ]
            
            booking_success = False
            for indicator in success_indicators:
                try:
                    if await self.page.locator(indicator).count() > 0:
                        booking_success = True
                        logger.info("✅ Найден индикатор успешного бронирования")
                        break
                except:
                    continue
            
            if booking_success:
                logger.info(f"🎉 Поставка {supply_id} успешно забронирована!")
                return True
            else:
                logger.info(f"🤔 Бронирование завершено, но статус неясен. Считаем успешным.")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка при бронировании поставки: {e}")
            return False

    async def find_available_slots(self) -> List[Dict]:
        """Найти доступные слоты для бронирования."""
        try:
            logger.info("🔍 Ищу доступные слоты...")
            
            # Переходим на страницу планирования
            await self.page.goto("https://seller.wildberries.ru/supplies/planning", wait_until="networkidle")
            await asyncio.sleep(3)
            
            # Ищем таблицу со слотами
            slots = []
            
            # Ищем элементы слотов (примерные селекторы)
            slot_elements = await self.page.query_selector_all('[data-testid*="slot"], .slot-item, .date-slot')
            
            for element in slot_elements:
                try:
                    # Извлекаем данные слота
                    date_text = await element.inner_text()
                    if date_text and "x" in date_text:
                        # Парсим дату и коэффициент
                        parts = date_text.split()
                        date = parts[0] if parts else "Неизвестно"
                        coef_text = [p for p in parts if "x" in p]
                        coefficient = coef_text[0].replace("x", "") if coef_text else "1"
                        
                        slots.append({
                            "date": date,
                            "coefficient": int(coefficient) if coefficient.isdigit() else 1,
                            "available": True
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга слота: {e}")
                    continue
            
            logger.info(f"✅ Найдено слотов: {len(slots)}")
            return slots
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска слотов: {e}")
            return []

    async def get_my_supplies(self) -> List[Dict]:
        """Получить список моих поставок."""
        try:
            logger.info("📦 Получаю список поставок...")
            
            # Переходим на страницу поставок
            await self.navigate_to_supplies_page()
            await asyncio.sleep(3)
            
            supplies = []
            
            # Ищем элементы поставок
            supply_elements = await self.page.query_selector_all('[data-testid*="supply"], .supply-item, .supply-card')
            
            for element in supply_elements:
                try:
                    # Извлекаем данные поставки
                    text = await element.inner_text()
                    if text:
                        # Парсим ID поставки
                        id_match = re.search(r'#(\d+)', text)
                        supply_id = id_match.group(1) if id_match else "N/A"
                        
                        # Парсим статус
                        status = "Неизвестно"
                        if "запланировано" in text.lower():
                            status = "Запланировано"
                        elif "не запланировано" in text.lower():
                            status = "Не запланировано"
                        elif "в пути" in text.lower():
                            status = "В пути"
                        
                        # Парсим дату
                        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                        date = date_match.group(1) if date_match else "Не указана"
                        
                        supplies.append({
                            "id": supply_id,
                            "status": status,
                            "date": date,
                            "text": text[:100] + "..." if len(text) > 100 else text
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга поставки: {e}")
                    continue
            
            logger.info(f"✅ Найдено поставок: {len(supplies)}")
            return supplies
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения поставок: {e}")
            return []
    
    async def auto_catch_supply(self, filters: dict = None, interval_ms: int = 1000) -> bool:
        """
        Автоматическая ловля поставок (улучшенная логика).
        
        Работает бесконечно, пока не забронирует слот или не будет остановлен вручную.
        Если нет подходящих дат - закрывает popup через ESC и продолжает поиск.
        
        Args:
            filters: Фильтры для дат и коэффициентов
                - dateFrom: начальная дата периода (YYYY-MM-DD)
                - dateTo: конечная дата периода (YYYY-MM-DD)
                - maxCoefficient: максимальный коэффициент (по умолчанию любой)
            interval_ms: Интервал между кликами в миллисекундах
            
        Returns:
            True если поставка запланирована, False если остановлено
        """
        try:
            logger.info("🎯 Запуск автоловли поставок...")
            logger.info(f"⏱️ Интервал: {interval_ms}ms")
            logger.info(f"📋 Фильтры: {filters}")
            
            # Переходим на страницу поставок
            await self.page.goto("https://seller.wildberries.ru/supplies-management/all-supplies", wait_until="networkidle")
            await asyncio.sleep(2)
            
            click_count = 0
            attempts_without_dates = 0
            
            while True:
                # Ищем кнопку "Запланировать поставку"
                button = await self._find_plan_button()
                
                if button:
                    # Проверяем доступность
                    is_disabled = await button.get_attribute('disabled')
                    if is_disabled:
                        logger.debug("⚠️ Кнопка недоступна, ждем...")
                        await asyncio.sleep(interval_ms / 1000)
                        continue
                    
                    # Кликаем на кнопку
                    await button.click()
                    click_count += 1
                    logger.info(f"✅ Клик #{click_count} по кнопке 'Запланировать поставку'")
                    
                    # Ждем появления модального окна
                    await asyncio.sleep(0.7)
                    
                    # Проверяем что модальное окно открылось
                    modal_opened = await self._check_modal_opened()
                    
                    if modal_opened:
                        logger.info("📋 Модальное окно открылось, ищем подходящую дату...")
                        
                        # Пытаемся выбрать подходящую дату
                        date_result = await self._select_date_in_modal(filters)
                        
                        if date_result == "BOOKED":
                            # Поставка успешно забронирована!
                            logger.info("🎉 ПОСТАВКА УСПЕШНО ЗАПЛАНИРОВАНА!")
                            logger.info(f"   Всего попыток: {click_count}")
                            logger.info(f"   Попыток без дат: {attempts_without_dates}")
                            
                            # Закрываем окно и завершаем (или продолжаем для новой поставки)
                            await self._close_modal_with_esc()
                            await asyncio.sleep(1)
                            
                            # Можно вернуть True для завершения или продолжить цикл
                            # return True  # Если нужно остановиться после первой брони
                            
                            # Продолжаем ловить следующие слоты
                            logger.info("🔄 Продолжаем поиск новых слотов...")
                            
                        elif date_result == "NO_DATES":
                            # Нет подходящих дат в модальном окне
                            logger.warning("⚠️ Подходящих дат не найдено в модальном окне")
                            attempts_without_dates += 1
                            
                            # Закрываем popup через ESC
                            logger.info("🔑 Закрываю popup через ESC...")
                            await self._close_modal_with_esc()
                            await asyncio.sleep(0.5)
                            
                            # Логируем статистику
                            if attempts_without_dates % 10 == 0:
                                logger.info(f"📊 Статистика: {attempts_without_dates} попыток без подходящих дат")
                            
                        else:
                            # Ошибка при работе с модальным окном
                            logger.warning("⚠️ Ошибка при обработке модального окна")
                            await self._close_modal_with_esc()
                            await asyncio.sleep(0.5)
                    else:
                        logger.debug("❌ Модальное окно не открылось после клика")
                    
                else:
                    logger.debug("❌ Кнопка 'Запланировать поставку' не найдена на странице")
                
                # Ждем перед следующей попыткой
                await asyncio.sleep(interval_ms / 1000)
                
        except asyncio.CancelledError:
            logger.info("⏹️ Автоловля остановлена пользователем")
            return False
        except Exception as e:
            logger.error(f"❌ Критическая ошибка автоловли: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _find_plan_button(self):
        """Найти кнопку 'Запланировать поставку'."""
        # Поиск по различным селекторам
        selectors = [
            'button.button_ymbakhzRx',
            'button:has-text("Запланировать")',
            'button:has-text("поставку")',
            'button[class*="fullWidth"]',
            'button[class*="button"]'
        ]
        
        for selector in selectors:
            try:
                button = await self.page.query_selector(selector)
                if button:
                    text = await button.inner_text()
                    if 'запланировать' in text.lower():
                        return button
            except:
                continue
        
        return None
    
    async def _check_modal_opened(self) -> bool:
        """Проверить открылось ли модальное окно."""
        try:
            modal = await self.page.query_selector('[role="dialog"], .modal, [class*="modal"], [class*="Modal"]')
            return modal is not None
        except:
            return False
    
    async def _select_date_in_modal(self, filters: dict = None) -> str:
        """
        Выбрать дату в модальном окне с учетом фильтров.
        
        Returns:
            "BOOKED" - успешно забронировано
            "NO_DATES" - нет подходящих дат
            "ERROR" - ошибка
        """
        try:
            await asyncio.sleep(1)
            
            # Парсим фильтры периода дат
            date_from = None
            date_to = None
            if filters:
                date_from_str = filters.get('dateFrom')
                date_to_str = filters.get('dateTo')
                max_coefficient = filters.get('maxCoefficient')
                
                if date_from_str:
                    from datetime import datetime
                    try:
                        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                    except:
                        logger.warning(f"⚠️ Неверный формат dateFrom: {date_from_str}")
                
                if date_to_str:
                    from datetime import datetime
                    try:
                        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                    except:
                        logger.warning(f"⚠️ Неверный формат dateTo: {date_to_str}")
            
            # Ищем ячейки календаря
            cells = await self.page.query_selector_all('td, div[role="gridcell"]')
            
            logger.info(f"🔍 Найдено ячеек календаря: {len(cells)}")
            
            suitable_dates_found = 0
            
            for cell in cells:
                try:
                    text = await cell.inner_text()
                    
                    # Проверяем что это дата (число)
                    if not text or not text.strip().isdigit():
                        continue
                    
                    day = int(text.strip())
                    
                    # Проверяем доступность ячейки
                    classes = await cell.get_attribute('class') or ''
                    if 'disabled' in classes.lower() or 'unavailable' in classes.lower():
                        continue
                    
                    # Извлекаем коэффициент если есть
                    coefficient = await self._extract_coefficient(cell)
                    
                    # Проверяем коэффициент
                    if max_coefficient is not None:
                        if coefficient > max_coefficient:
                            logger.debug(f"   День {day}: коэфф {coefficient}x > {max_coefficient}x (пропускаем)")
                            continue
                    
                    # TODO: Проверка даты по периоду (требует определения текущего месяца/года из календаря)
                    # Пока считаем что дата подходит по коэффициенту
                    
                    suitable_dates_found += 1
                    
                    # Кликаем на дату
                    logger.info(f"📅 Найдена подходящая дата: день {day}, коэффициент: {coefficient}x")
                    logger.info(f"   Кликаем на ячейку...")
                    
                    await cell.click()
                    await asyncio.sleep(0.7)
                    
                    # Ищем кнопку финального подтверждения
                    confirm_clicked = await self._click_final_confirm()
                    
                    if confirm_clicked:
                        logger.info("✅ Финальное подтверждение нажато - поставка забронирована!")
                        return "BOOKED"
                    else:
                        # Не удалось подтвердить, пробуем следующую дату
                        logger.warning("⚠️ Не удалось нажать кнопку подтверждения")
                        # Не закрываем окно, пробуем следующую дату
                        continue
                        
                except Exception as e:
                    logger.debug(f"   Ошибка обработки ячейки: {e}")
                    continue
            
            # Если дошли сюда - подходящих дат не найдено
            if suitable_dates_found == 0:
                logger.warning("⚠️ Подходящих дат в календаре не найдено")
                return "NO_DATES"
            else:
                logger.warning(f"⚠️ Найдено {suitable_dates_found} подходящих дат, но не удалось забронировать")
                return "NO_DATES"
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора даты в модальном окне: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "ERROR"
    
    async def _extract_coefficient(self, cell) -> int:
        """Извлечь коэффициент из ячейки."""
        try:
            text = await cell.inner_text()
            # Ищем паттерн "x0", "x1", "x2" и т.д.
            import re
            match = re.search(r'x(\d+)', text.lower())
            if match:
                return int(match.group(1))
            
            # Проверяем на "Бесплатно"
            if 'бесплатно' in text.lower() or '0x' in text.lower():
                return 0
                
            return 1  # По умолчанию
        except:
            return 1
    
    async def _click_final_confirm(self) -> bool:
        """Нажать финальную кнопку подтверждения."""
        try:
            # Ждем кнопку подтверждения
            await asyncio.sleep(0.5)
            
            # Ищем кнопку
            selectors = [
                'button:has-text("Запланировать")',
                'button:has-text("Подтвердить")',
                'button[class*="primary"]',
                'button[type="submit"]'
            ]
            
            for selector in selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        await button.click()
                        logger.info("✅ Кнопка подтверждения нажата")
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
            
            return False
        except Exception as e:
            logger.error(f"Ошибка нажатия подтверждения: {e}")
            return False
    
    async def _close_modal(self):
        """Закрыть модальное окно (старый метод для обратной совместимости)."""
        await self._close_modal_with_esc()
    
    async def _close_modal_with_esc(self):
        """
        Надежное закрытие модального окна через ESC.
        Пытается несколько раз если не получилось с первого раза.
        """
        try:
            # Проверяем есть ли открытое модальное окно
            modal_exists = await self._check_modal_opened()
            
            if not modal_exists:
                logger.debug("   Модальное окно уже закрыто")
                return
            
            # Пробуем ESC несколько раз
            for attempt in range(3):
                logger.debug(f"   Нажимаю ESC (попытка {attempt + 1}/3)...")
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.3)
                
                # Проверяем закрылось ли окно
                modal_exists = await self._check_modal_opened()
                if not modal_exists:
                    logger.debug("   ✅ Модальное окно закрыто через ESC")
                    return
            
            # Если ESC не помог, пробуем найти кнопку закрытия
            logger.debug("   ESC не сработал, ищу кнопку закрытия...")
            close_selectors = [
                'button[aria-label="Close"]',
                'button[aria-label="Закрыть"]',
                'button.close',
                '[class*="close"]',
                '[class*="Close"]',
                'button:has-text("×")',
                'button:has-text("✕")'
            ]
            
            for selector in close_selectors:
                try:
                    close_btn = await self.page.query_selector(selector)
                    if close_btn:
                        await close_btn.click()
                        await asyncio.sleep(0.3)
                        logger.debug(f"   ✅ Модальное окно закрыто через кнопку")
                        return
                except:
                    continue
            
            # Последняя попытка - клик вне модального окна (на overlay)
            logger.debug("   Кнопка не найдена, пытаюсь кликнуть на overlay...")
            try:
                overlay = await self.page.query_selector('[class*="overlay"], [class*="backdrop"], [class*="Overlay"]')
                if overlay:
                    await overlay.click()
                    await asyncio.sleep(0.3)
                    logger.debug("   ✅ Модальное окно закрыто через клик на overlay")
            except:
                pass
                
        except Exception as e:
            logger.debug(f"   ⚠️ Ошибка при закрытии модального окна: {e}")
            # Не критично, продолжаем работу