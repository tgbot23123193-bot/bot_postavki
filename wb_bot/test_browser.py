"""
Тестовый скрипт для проверки браузерной автоматизации.
"""

import asyncio
import sys
from .app.services.browser_automation import WBBrowserAutomation


async def main():
    """Главная функция для тестирования."""
    
    print("=" * 50)
    print("🌐 ТЕСТ БРАУЗЕРНОЙ АВТОМАТИЗАЦИИ WB")
    print("=" * 50)
    
    # Запускаем браузер
    print("\n1. Запускаю браузер...")
    browser = WBBrowserAutomation(headless=False)
    
    try:
        browser.start_browser()
        print("✅ Браузер запущен успешно!")
        
        # Пробуем загрузить куки
        print("\n2. Проверяю сохраненные куки...")
        has_cookies = browser.load_cookies()
        
        if has_cookies:
            print("🍪 Куки найдены, пробую войти автоматически...")
        else:
            print("❌ Куки не найдены, потребуется ручной вход")
            
            # Запрашиваем телефон
            phone = input("\n📱 Введите номер телефона (+79991234567): ")
            
            print(f"\n3. Начинаю вход с номером {phone[:4]}****...")
            success = await browser.login(phone)
            
            if success:
                print("✅ Вход выполнен успешно!")
            else:
                print("❌ Не удалось войти")
                return
        
        # Меню действий
        while True:
            print("\n" + "=" * 50)
            print("ВЫБЕРИТЕ ДЕЙСТВИЕ:")
            print("1. Найти доступные слоты")
            print("2. Забронировать поставку")
            print("3. Автоматический мониторинг")
            print("4. Выход")
            print("=" * 50)
            
            choice = input("\nВаш выбор (1-4): ")
            
            if choice == "1":
                print("\n🔍 Ищу доступные слоты...")
                slots = await browser.find_available_slots()
                
                if slots:
                    print(f"\n✅ Найдено {len(slots)} слотов:")
                    for i, slot in enumerate(slots[:10], 1):
                        print(f"  {i}. 📅 {slot['date']} - Коэф: x{slot['coefficient']}")
                else:
                    print("😔 Слоты не найдены")
                    
            elif choice == "2":
                supply_id = input("\nВведите ID поставки: ")
                date = input("Введите дату (YYYY-MM-DD): ")
                
                print(f"\n📅 Бронирую поставку {supply_id} на {date}...")
                success = await browser.book_supply_slot(supply_id, date)
                
                if success:
                    print("✅ Успешно забронировано!")
                else:
                    print("❌ Не удалось забронировать")
                    
            elif choice == "3":
                supply_id = input("\nВведите ID поставки: ")
                start_date = input("Начальная дата (YYYY-MM-DD): ")
                end_date = input("Конечная дата (YYYY-MM-DD): ")
                max_coef = float(input("Макс. коэффициент (1-5): "))
                
                print(f"\n🤖 Запускаю автомониторинг...")
                success = await browser.monitor_and_book(
                    supply_id=supply_id,
                    start_date=start_date,
                    end_date=end_date,
                    max_coefficient=max_coef,
                    check_interval=5
                )
                
                if success:
                    print("✅ Поставка забронирована автоматически!")
                else:
                    print("❌ Не удалось забронировать автоматически")
                    
            elif choice == "4":
                print("\n👋 До свидания!")
                break
            else:
                print("❌ Неверный выбор")
                
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🔚 Закрываю браузер...")
        browser.close_browser()
        print("✅ Готово!")


if __name__ == "__main__":
    print("\n🚀 Запуск тестового скрипта браузерной автоматизации\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)


