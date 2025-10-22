"""
Тестовый скрипт для проверки работы автобронирования.
"""
import asyncio
from app.services.auto_booking_service import auto_booking_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def test_auto_booking_service():
    """Тестирует работу сервиса автобронирования."""
    
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ СЕРВИСА АВТОБРОНИРОВАНИЯ")
    print("=" * 60)
    
    # Тестовые данные
    test_user_id = 123456789
    test_supply_id = "WB-TEST-001"
    test_supply_name = "Тестовая поставка"
    test_warehouse_id = 1234
    test_warehouse_name = "Тестовый склад"
    test_date_from = "2024-01-01"
    test_date_to = "2024-12-31"
    
    print("\n📋 Тестовые данные:")
    print(f"   User ID: {test_user_id}")
    print(f"   Supply: {test_supply_name} ({test_supply_id})")
    print(f"   Warehouse: {test_warehouse_name} ({test_warehouse_id})")
    print(f"   Period: {test_date_from} - {test_date_to}")
    
    # Callback функции для тестирования
    success_called = False
    error_called = False
    success_data = None
    error_msg = None
    
    async def on_success(result):
        nonlocal success_called, success_data
        success_called = True
        success_data = result
        print(f"\n✅ SUCCESS CALLBACK вызван!")
        print(f"   Результат: {result}")
    
    async def on_error(error):
        nonlocal error_called, error_msg
        error_called = True
        error_msg = error
        print(f"\n❌ ERROR CALLBACK вызван!")
        print(f"   Ошибка: {error}")
    
    # Тест 1: Запуск автобронирования
    print("\n" + "=" * 60)
    print("ТЕСТ 1: Запуск автобронирования")
    print("=" * 60)
    
    try:
        started = await auto_booking_service.start_auto_booking(
            user_id=test_user_id,
            supply_id=test_supply_id,
            supply_name=test_supply_name,
            warehouse_id=test_warehouse_id,
            warehouse_name=test_warehouse_name,
            date_from=test_date_from,
            date_to=test_date_to,
            max_coefficient=1,
            check_interval=5,  # 5 секунд для теста
            mode="api",
            on_success=on_success,
            on_error=on_error
        )
        
        if started:
            print("✅ Автобронирование успешно запущено")
        else:
            print("❌ Не удалось запустить автобронирование")
            return
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Тест 2: Проверка активности
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Проверка статуса")
    print("=" * 60)
    
    is_active = auto_booking_service.is_active(test_user_id)
    print(f"   Активно: {is_active}")
    
    session = auto_booking_service.get_session(test_user_id)
    if session:
        print(f"   Сессия найдена:")
        print(f"     - Supply: {session.supply_name}")
        print(f"     - Warehouse: {session.warehouse_name}")
        print(f"     - Status: {session.status}")
        print(f"     - Mode: {session.mode}")
        print(f"     - Interval: {session.check_interval}s")
    else:
        print("   ❌ Сессия не найдена")
    
    # Даем время на несколько проверок
    print("\n" + "=" * 60)
    print("⏳ Ждем 15 секунд для проверки работы...")
    print("=" * 60)
    
    for i in range(15):
        await asyncio.sleep(1)
        session = auto_booking_service.get_session(test_user_id)
        if session:
            print(f"   [{i+1}/15] Проверок: {session.checks_count}, Статус: {session.status}")
        else:
            print(f"   [{i+1}/15] Сессия завершена")
            break
    
    # Тест 3: Остановка автобронирования
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Остановка автобронирования")
    print("=" * 60)
    
    if auto_booking_service.is_active(test_user_id):
        stopped = await auto_booking_service.stop_auto_booking(test_user_id)
        if stopped:
            print("✅ Автобронирование успешно остановлено")
        else:
            print("❌ Не удалось остановить автобронирование")
    else:
        print("ℹ️ Автобронирование уже неактивно")
    
    # Проверяем финальный статус
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ")
    print("=" * 60)
    
    print(f"   Success callback вызван: {success_called}")
    if success_data:
        print(f"   Success data: {success_data}")
    
    print(f"   Error callback вызван: {error_called}")
    if error_msg:
        print(f"   Error message: {error_msg}")
    
    print(f"   Активная сессия: {auto_booking_service.is_active(test_user_id)}")
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


async def test_double_start():
    """Тестирует запрет повторного запуска автобронирования."""
    
    print("\n\n" + "=" * 60)
    print("🧪 ТЕСТ: Повторный запуск (должен быть заблокирован)")
    print("=" * 60)
    
    test_user_id = 987654321
    
    # Первый запуск
    started1 = await auto_booking_service.start_auto_booking(
        user_id=test_user_id,
        supply_id="TEST-1",
        supply_name="Test 1",
        warehouse_id=1,
        warehouse_name="WH 1",
        date_from="2024-01-01",
        date_to="2024-12-31",
        check_interval=60,
        mode="api"
    )
    
    print(f"   Первый запуск: {'✅ успешно' if started1 else '❌ неудачно'}")
    
    # Второй запуск (должен быть заблокирован)
    started2 = await auto_booking_service.start_auto_booking(
        user_id=test_user_id,
        supply_id="TEST-2",
        supply_name="Test 2",
        warehouse_id=2,
        warehouse_name="WH 2",
        date_from="2024-01-01",
        date_to="2024-12-31",
        check_interval=60,
        mode="api"
    )
    
    print(f"   Второй запуск: {'❌ не заблокирован!' if started2 else '✅ заблокирован'}")
    
    # Очистка
    await auto_booking_service.stop_auto_booking(test_user_id)
    
    print("=" * 60)


async def main():
    """Главная функция для запуска всех тестов."""
    try:
        # Запускаем тесты
        await test_auto_booking_service()
        await test_double_start()
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

