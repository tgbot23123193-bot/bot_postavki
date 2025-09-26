#!/usr/bin/env python3
"""
Расширенный скрипт для запуска и управления браузером пользователя.
Поддерживает различные команды и режимы работы.
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from app.services.browser_manager import BrowserManager
from app.services.redistribution_service import get_redistribution_service
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)

class BrowserLauncher:
    """Класс для управления браузером пользователя."""
    
    def __init__(self):
        self.browser_manager = None
        self.browser = None
        
    async def launch_browser(self, user_id: int, headless: bool = False):
        """Запускает браузер для пользователя."""
        try:
            logger.info(f"🚀 Запуск браузера для пользователя {user_id} (headless={headless})")
            
            # Создаем браузер менеджер
            self.browser_manager = BrowserManager()
            
            # Запускаем браузер
            self.browser = await self.browser_manager.get_browser(
                user_id=user_id,
                headless=headless,
                debug_mode=True
            )
            
            if not self.browser:
                logger.error(f"❌ Не удалось запустить браузер для пользователя {user_id}")
                return False
            
            logger.info(f"✅ Браузер запущен для пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске браузера: {e}")
            return False
    
    async def open_redistribution_page(self, user_id: int):
        """Открывает страницу перераспределения."""
        try:
            if not self.browser:
                print("❌ Браузер не запущен")
                return
            
            redistribution_service = get_redistribution_service(self.browser_manager)
            result = await redistribution_service.open_redistribution_page(user_id)
            
            if result["success"]:
                print("✅ Страница перераспределения открыта")
            else:
                print(f"❌ Ошибка: {result['error']}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при открытии страницы: {e}")
    
    async def get_warehouses(self, user_id: int):
        """Получает список складов."""
        try:
            if not self.browser:
                print("❌ Браузер не запущен")
                return
            
            redistribution_service = get_redistribution_service(self.browser_manager)
            result = await redistribution_service.get_available_warehouses(user_id)
            
            if result["success"]:
                warehouses = result["warehouses"]
                print(f"✅ Найдено складов: {len(warehouses)}")
                for i, warehouse in enumerate(warehouses, 1):
                    print(f"  {i}. {warehouse['name']}")
            else:
                print(f"❌ Ошибка: {result['error']}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при получении складов: {e}")
    
    async def interactive_mode(self, user_id: int):
        """Интерактивный режим управления браузером."""
        print(f"\n🎮 Интерактивный режим для пользователя {user_id}")
        print("💡 Доступные команды:")
        print("  open - Открыть страницу перераспределения")
        print("  warehouses - Получить список складов")
        print("  url - Показать текущий URL")
        print("  screenshot - Сделать скриншот")
        print("  goto <url> - Перейти на URL")
        print("  quit - Выход")
        
        while True:
            try:
                command = input("\n🔸 Введите команду: ").strip().lower()
                
                if command == "quit":
                    break
                elif command == "open":
                    await self.open_redistribution_page(user_id)
                elif command == "warehouses":
                    await self.get_warehouses(user_id)
                elif command == "url":
                    if self.browser and self.browser.page:
                        print(f"🌐 Текущий URL: {self.browser.page.url}")
                    else:
                        print("❌ Страница не доступна")
                elif command == "screenshot":
                    if self.browser and self.browser.page:
                        screenshot_path = f"screenshots_{user_id}/manual_screenshot.png"
                        Path(f"screenshots_{user_id}").mkdir(exist_ok=True)
                        await self.browser.page.screenshot(path=screenshot_path)
                        print(f"📸 Скриншот сохранен: {screenshot_path}")
                    else:
                        print("❌ Страница не доступна")
                elif command.startswith("goto "):
                    url = command[5:].strip()
                    if self.browser and self.browser.page:
                        await self.browser.page.goto(url)
                        print(f"🌐 Переход на: {url}")
                    else:
                        print("❌ Страница не доступна")
                elif command == "help":
                    print("💡 Доступные команды:")
                    print("  open - Открыть страницу перераспределения")
                    print("  warehouses - Получить список складов")
                    print("  url - Показать текущий URL")
                    print("  screenshot - Сделать скриншот")
                    print("  goto <url> - Перейти на URL")
                    print("  quit - Выход")
                else:
                    print("❌ Неизвестная команда. Введите 'help' для справки")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")
    
    async def close(self):
        """Закрывает браузер."""
        if self.browser_manager:
            await self.browser_manager.close_all()
            logger.info("🔒 Браузер закрыт")

async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Запуск браузера пользователя")
    parser.add_argument("user_id", type=int, help="ID пользователя")
    parser.add_argument("--headless", action="store_true", help="Запуск в headless режиме")
    parser.add_argument("--interactive", action="store_true", help="Интерактивный режим")
    parser.add_argument("--open-redistribution", action="store_true", help="Сразу открыть страницу перераспределения")
    parser.add_argument("--get-warehouses", action="store_true", help="Получить список складов")
    
    args = parser.parse_args()
    
    launcher = BrowserLauncher()
    
    try:
        # Запускаем браузер
        success = await launcher.launch_browser(args.user_id, args.headless)
        if not success:
            return
        
        print(f"✅ Браузер запущен для пользователя {args.user_id}")
        if launcher.browser:
            print(f"📂 Профиль: {launcher.browser.user_data_dir}")
            if launcher.browser.page:
                print(f"🌐 Текущая страница: {launcher.browser.page.url}")
        
        # Выполняем команды
        if args.open_redistribution:
            await launcher.open_redistribution_page(args.user_id)
        
        if args.get_warehouses:
            await launcher.get_warehouses(args.user_id)
        
        if args.interactive:
            await launcher.interactive_mode(args.user_id)
        else:
            print("\n💡 Браузер запущен. Нажмите Ctrl+C для завершения")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        await launcher.close()

if __name__ == "__main__":
    asyncio.run(main())


