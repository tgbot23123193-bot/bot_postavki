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
from playwright_stealth import stealth_async
from ..utils.logger import get_logger

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
    
    async def start_browser(self) -> bool:
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
            
            # Запускаем браузер
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=browser_args,
                slow_mo=50 if self.debug_mode else 0,  # Замедление для отладки
                devtools=self.debug_mode and not self.headless
            )
            
            # Создаем контекст с реальными настройками
            viewport = random.choice(self.viewports)
            user_agent = random.choice(self.user_agents)
            
            self.context = await self.browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
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
            
            # Создаем страницу
            self.page = await self.context.new_page()
            
            # Применяем stealth режим для максимального обхода детекции
            await stealth_async(self.page)
            
            # Дополнительные скрипты для обхода детекции
            await self._inject_stealth_scripts()
            
            # Загружаем куки если есть
            await self._load_cookies()
            
            logger.info("✅ Браузер запущен успешно с полным обходом детекции")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска браузера: {e}")
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
    
    async def login_step1_phone(self, phone: str) -> bool:
        """Шаг 1: Ввод номера телефона с максимальной человечностью."""
        try:
            logger.info("🔐 Начинаю процесс входа в WB...")
            
            # Пробуем разные страницы входа
            login_urls = [
                "https://seller.wildberries.ru/",
                "https://seller.wildberries.ru/login",
                "https://passport.wildberries.ru/signin"
            ]
            
            page_loaded = False
            for url in login_urls:
                try:
                    logger.info(f"🔗 Пробую загрузить: {url}")
                    
                    # Переходим на страницу
                    response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    if response and response.status == 200:
                        logger.info(f"✅ Страница загружена: {url}")
                        page_loaded = True
                        break
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка загрузки {url}: {e}")
                    continue
            
            if not page_loaded:
                logger.error("❌ Не удалось загрузить ни одну страницу входа")
                return False
            
            # Ждем полной загрузки страницы
            await asyncio.sleep(random.uniform(2, 4))
            
            if self.debug_mode:
                await self.page.screenshot(path="wb_login_page.png")
                logger.info("📸 Скриншот страницы сохранен")
            
            # Умный поиск поля телефона
            phone_selectors = [
                # Специфичные для WB
                'input[name="phone"]',
                'input[name="phoneNumber"]',
                'input[name="login"]',
                'input[type="tel"]',
                
                # По placeholder
                'input[placeholder*="телефон" i]',
                'input[placeholder*="номер" i]',
                'input[placeholder*="phone" i]',
                
                # По ID
                '#phone',
                '#phoneNumber',
                '#login',
                
                # По классам
                '.phone-input input',
                '.login-input input',
                'input[class*="phone" i]',
                'input[class*="login" i]',
                
                # Fallback - первый видимый input
                'form input:first-of-type',
                'input:first-of-type'
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
                if self.debug_mode:
                    # Показываем все input элементы для отладки
                    inputs = await self.page.query_selector_all('input')
                    logger.info(f"🔍 Найдено {len(inputs)} input элементов:")
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
            
            # Человеческий ввод номера
            logger.info(f"📱 Ввожу номер телефона: {phone}")
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
            
            # Ждем появления поля для SMS кода
            await asyncio.sleep(random.uniform(2, 4))
            
            # Проверяем что SMS отправлен
            sms_indicators = [
                'input[name="code"]',
                'input[name="smsCode"]',
                'input[placeholder*="код" i]',
                'text=код отправлен',
                'text=SMS отправлен',
                '.sms-code'
            ]
            
            sms_sent = False
            for indicator in sms_indicators:
                try:
                    if await self.page.query_selector(indicator):
                        sms_sent = True
                        break
                except:
                    continue
            
            if sms_sent:
                logger.info("✅ SMS код запрошен успешно")
                await self._save_cookies()
                return True
            else:
                logger.warning("⚠️ Не удалось определить отправку SMS")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка ввода номера телефона: {e}")
            return False
    
    async def login_step2_sms(self, sms_code: str) -> bool:
        """Шаг 2: Ввод SMS кода."""
        try:
            logger.info(f"📨 Ввожу SMS код: {sms_code}")
            
            # Ищем поле SMS кода
            sms_selectors = [
                'input[name="code"]',
                'input[name="smsCode"]',
                'input[name="verificationCode"]',
                'input[placeholder*="код" i]',
                'input[type="text"]:not([name="phone"])',
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
            
            # Человеческий ввод SMS кода
            await self._human_type(sms_input, sms_code)
            
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
        """Закрытие браузера с сохранением куки."""
        try:
            if self.page:
                await self._save_cookies()
            
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("🔚 Браузер закрыт")
            
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

