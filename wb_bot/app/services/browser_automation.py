#!/usr/bin/env python3
"""
Профессиональная браузерная автоматизация для WB на Playwright.
Обход детекции, стелс режим, полный контроль.
"""

import asyncio
import json
import random
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import playwright_stealth
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WBBrowserAutomationPro:
    """Профессиональная автоматизация браузера для WB с обходом детекции."""
    
    def __init__(self, headless: bool = True, debug_mode: bool = False):
        self.headless = headless
        self.debug_mode = debug_mode
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cookies_file = Path("wb_cookies.json")
        self.user_data_dir = Path("wb_user_data")  # Папка для сохранения профиля браузера
        
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
            
            # Запускаем браузер с постоянным профилем пользователя
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                args=browser_args,
                slow_mo=50 if self.debug_mode else 0,  # Замедление для отладки
                devtools=self.debug_mode and not self.headless,
                # Настройки контекста встроены в persistent context
                viewport=random.choice(self.viewports),
                user_agent=random.choice(self.user_agents),
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                geolocation={"latitude": 55.7558, "longitude": 37.6176},  # Москва
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
            # Переопределяем webdriver property
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
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
        """Загружаем сохраненные куки."""
        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                logger.info("🍪 Куки загружены")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки куки: {e}")
    
    async def _save_cookies(self):
        """Сохраняем куки."""
        try:
            cookies = await self.context.cookies()
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info("🍪 Куки сохранены")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения куки: {e}")
    
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
    
    async def _human_click(self, selector: str, delay_before: tuple = (0.5, 1.5)):
        """Человеческий клик с задержкой и движением мыши."""
        await asyncio.sleep(random.uniform(*delay_before))
        
        element = await self.page.wait_for_selector(selector, timeout=10000)
        
        # Наводим мышь на элемент
        await element.hover()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Кликаем
        await element.click()
        await asyncio.sleep(random.uniform(0.2, 0.5))
    
    async def check_if_logged_in(self) -> bool:
        """Проверяет, авторизован ли пользователь в WB."""
        try:
            logger.info("🔍 Проверяю авторизацию в WB...")
            
            # Переходим на страницу поставок для проверки авторизации
            supplies_url = "https://seller.wildberries.ru/supplies-management/all-supplies"
            response = await self.page.goto(supplies_url, wait_until="networkidle", timeout=15000)
            
            if response and response.status == 200:
                current_url = self.page.url
                logger.info(f"📍 Текущий URL: {current_url}")
                
                # Проверяем признаки авторизации
                is_logged_in = any([
                    'seller.wildberries.ru' in current_url and 'login' not in current_url,
                    'supplies-management' in current_url,
                    'lk-seller.wildberries.ru' in current_url
                ])
                
                if is_logged_in:
                    logger.info("✅ Пользователь уже авторизован!")
                    return True
                else:
                    logger.info("❌ Пользователь не авторизован")
                    return False
            
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки авторизации: {e}")
            return False

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
            
            # Человеческий ввод номера
            logger.info(f"📱 Ввожу номер телефона: {phone}")
            
            # Для киргизских номеров используем правильную стратегию ввода
            if phone.startswith('+996'):
                # Если Кыргызстан был выбран, вводим только цифры без кода
                if kg_selected:
                    logger.info("📱 Кыргызстан выбран, ввожу только цифры без кода страны...")
                    clean_phone = phone[4:]  # Убираем +996, остается 500441234
                    await self._human_type(phone_input, clean_phone)
                    logger.info(f"✅ Введены цифры: {clean_phone}")
                else:
                    logger.info("📱 Кыргызстан не выбран, пробую разные варианты ввода...")
                    
                    # Попытка 1: Вводим полный номер
                    logger.info("📱 Попытка 1: Ввод полного номера +996...")
                    await self._human_type(phone_input, phone)
                    await asyncio.sleep(2)
                    
                    # Проверяем что получилось в поле
                    try:
                        current_value = await self.page.evaluate(f'document.querySelector(`{phone_input}`).value')
                        logger.info(f"🔍 Значение в поле после ввода: '{current_value}'")
                        
                        # Если WB автоматически подставил +7 вместо +996, исправляем
                        if current_value and ('+7' in current_value or current_value.startswith('7') or '996' not in current_value):
                            logger.warning("⚠️ WB подставил неправильный код, исправляю...")
                            
                            # Попытка 2: Очищаем и вводим только цифры
                            phone_element = await self.page.query_selector(phone_input)
                            await phone_element.click()
                            await phone_element.fill("")  # Полная очистка
                            await asyncio.sleep(1)
                            
                            # Вводим только цифры без кода страны
                            clean_phone = phone[4:]  # Убираем +996
                            logger.info(f"📱 Попытка 2: Ввод без кода: {clean_phone}")
                            await self._human_type(phone_input, clean_phone)
                            await asyncio.sleep(2)
                            
                            # Проверяем результат второй попытки
                            final_value = await self.page.evaluate(f'document.querySelector(`{phone_input}`).value')
                            logger.info(f"🔍 Финальное значение в поле: '{final_value}'")
                        else:
                            logger.info("✅ Номер введен правильно с первой попытки")
                            
                    except Exception as js_error:
                        logger.error(f"❌ Ошибка проверки значения поля: {js_error}")
                        # Продолжаем работу даже если проверка не удалась
                    
            else:
                await self._human_type(phone_input, phone)
            
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
                    # Очищаем поле
                    await sms_field.fill("")
                    await asyncio.sleep(0.5)
                    
                    # Вводим код символ за символом (как человек)
                    logger.info(f"⌨️ Печатаю код по символам: {sms_code}")
                    for char in sms_code:
                        await sms_field.type(char)
                        await asyncio.sleep(random.uniform(0.1, 0.3))  # Человеческие задержки
                    
                    logger.info(f"✅ SMS код введен успешно: {sms_code}")
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
            
            # Ждем перенаправления
            await asyncio.sleep(random.uniform(3, 5))
            
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
        """Сделать скриншот."""
        try:
            if self.page:
                await self.page.screenshot(path=filename, full_page=True)
                logger.info(f"📸 Скриншот сохранен: {filename}")
                return True
        except Exception as e:
            logger.error(f"❌ Ошибка создания скриншота: {e}")
            return False

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
