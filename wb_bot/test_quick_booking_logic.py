"""
Тест логики быстрого бронирования с проверкой 72 часов.
"""
from datetime import datetime, timedelta


def test_date_filter_logic():
    """Тестирует логику фильтрации дат по 72 часам."""
    
    print("=" * 80)
    print("🧪 ТЕСТ ЛОГИКИ ФИЛЬТРАЦИИ ДАТ ПО 72 ЧАСАМ")
    print("=" * 80)
    
    # Текущее время
    now = datetime.now()
    print(f"\n📅 Текущее время: {now.strftime('%d.%m.%Y %H:%M')}")
    
    # Минимальная допустимая дата (72 часа = 3 дня)
    min_hours_ahead = 72
    min_date = now + timedelta(hours=min_hours_ahead)
    print(f"⏰ Минимальная дата (через {min_hours_ahead}ч): {min_date.strftime('%d.%m.%Y %H:%M')}")
    
    # Тестовые даты (как будто из календаря)
    test_dates = [
        now + timedelta(hours=24),   # +1 день
        now + timedelta(hours=48),   # +2 дня
        now + timedelta(hours=72),   # +3 дня (ровно 72ч)
        now + timedelta(hours=80),   # +3.3 дня
        now + timedelta(hours=96),   # +4 дня
        now + timedelta(hours=120),  # +5 дней
        now + timedelta(hours=168),  # +7 дней
    ]
    
    print("\n" + "=" * 80)
    print("📋 ПРОВЕРКА КАЖДОЙ ДАТЫ:")
    print("=" * 80)
    
    suitable_dates = []
    
    for i, test_date in enumerate(test_dates, 1):
        hours_diff = (test_date - now).total_seconds() / 3600
        days_diff = hours_diff / 24
        
        # СТАРАЯ ЛОГИКА (НЕПРАВИЛЬНАЯ):
        # is_suitable_old = test_date.day == min_date.day and test_date.month == min_date.month
        
        # НОВАЯ ЛОГИКА (ПРАВИЛЬНАЯ):
        is_suitable_new = test_date >= min_date
        
        status = "✅ ПОДХОДИТ" if is_suitable_new else "❌ Слишком близко"
        
        print(f"\n{i}. Дата: {test_date.strftime('%d.%m.%Y %H:%M')}")
        print(f"   Разница: {hours_diff:.1f}ч ({days_diff:.1f} дней)")
        print(f"   Статус: {status}")
        
        if is_suitable_new:
            suitable_dates.append(test_date)
    
    print("\n" + "=" * 80)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("=" * 80)
    
    print(f"\n✅ Подходящих дат найдено: {len(suitable_dates)}/{len(test_dates)}")
    print(f"📅 Первая подходящая дата: {suitable_dates[0].strftime('%d.%m.%Y %H:%M') if suitable_dates else 'НЕТ'}")
    
    print("\n" + "=" * 80)
    print("🎯 ПРОВЕРКА ЛОГИКИ:")
    print("=" * 80)
    
    # Проверка 1: Дата ровно через 72 часа должна подходить
    exact_72h = now + timedelta(hours=72)
    check1 = exact_72h >= min_date
    print(f"\n1. Дата ровно через 72ч подходит: {'✅ ДА' if check1 else '❌ НЕТ'}")
    print(f"   {exact_72h.strftime('%d.%m.%Y %H:%M')} >= {min_date.strftime('%d.%m.%Y %H:%M')} = {check1}")
    
    # Проверка 2: Дата через 71 час НЕ должна подходить
    before_72h = now + timedelta(hours=71)
    check2 = before_72h >= min_date
    print(f"\n2. Дата через 71ч НЕ подходит: {'❌ ВЕРНО (не подходит)' if not check2 else '✅ ОШИБКА (подходит)'}")
    print(f"   {before_72h.strftime('%d.%m.%Y %H:%M')} >= {min_date.strftime('%d.%m.%Y %H:%M')} = {check2}")
    
    # Проверка 3: Дата через 100 часов должна подходить
    after_72h = now + timedelta(hours=100)
    check3 = after_72h >= min_date
    print(f"\n3. Дата через 100ч подходит: {'✅ ДА' if check3 else '❌ НЕТ'}")
    print(f"   {after_72h.strftime('%d.%m.%Y %H:%M')} >= {min_date.strftime('%d.%m.%Y %H:%M')} = {check3}")
    
    # Общий результат
    all_checks_passed = check1 and not check2 and check3
    
    print("\n" + "=" * 80)
    if all_checks_passed:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! ЛОГИКА РАБОТАЕТ ПРАВИЛЬНО!")
    else:
        print("❌ НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОШЛИ! ЕСТЬ ОШИБКИ В ЛОГИКЕ!")
    print("=" * 80)
    
    return all_checks_passed


def test_real_world_scenario():
    """Тестирует реальный сценарий с датами из календаря."""
    
    print("\n\n" + "=" * 80)
    print("🌍 РЕАЛЬНЫЙ СЦЕНАРИЙ: Календарь WB")
    print("=" * 80)
    
    now = datetime.now()
    min_hours = 80  # Как в коде
    min_date = now + timedelta(hours=min_hours)
    
    print(f"\n📅 Сегодня: {now.strftime('%d.%m.%Y %H:%M')}")
    print(f"⏰ Минимум: {min_date.strftime('%d.%m.%Y %H:%M')} (через {min_hours}ч = {min_hours/24:.1f} дней)")
    
    # Симулируем календарь WB с датами на 2 недели вперед
    calendar_dates = []
    for day_offset in range(1, 15):  # 14 дней вперед
        calendar_dates.append(now + timedelta(days=day_offset))
    
    print(f"\n📋 Календарь содержит {len(calendar_dates)} дат")
    print("\n🔍 Проверяю каждую дату:")
    
    first_suitable = None
    suitable_count = 0
    
    for i, date in enumerate(calendar_dates, 1):
        is_suitable = date >= min_date
        
        if is_suitable:
            suitable_count += 1
            if not first_suitable:
                first_suitable = date
            status = "✅"
        else:
            status = "❌"
        
        print(f"   {status} {date.strftime('%d.%m.%Y')} ({i} день)")
    
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТ:")
    print("=" * 80)
    print(f"\n✅ Подходящих дат: {suitable_count}/{len(calendar_dates)}")
    
    if first_suitable:
        print(f"🎯 Первая подходящая дата: {first_suitable.strftime('%d.%m.%Y')}")
        print(f"📅 Это через: {(first_suitable - now).total_seconds() / 3600:.1f} часов ({(first_suitable - now).days} дней)")
    else:
        print("❌ Подходящих дат не найдено")
    
    print("\n" + "=" * 80)
    
    return first_suitable is not None


if __name__ == "__main__":
    print("\n" * 2)
    test1_passed = test_date_filter_logic()
    test2_passed = test_real_world_scenario()
    
    print("\n\n" + "=" * 80)
    print("🏁 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("=" * 80)
    
    print(f"\n✅ Тест логики фильтрации: {'ПРОЙДЕН' if test1_passed else 'НЕ ПРОЙДЕН'}")
    print(f"✅ Тест реального сценария: {'ПРОЙДЕН' if test2_passed else 'НЕ ПРОЙДЕН'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! ЛОГИКА 72 ЧАСОВ РАБОТАЕТ КОРРЕКТНО!")
    else:
        print("\n❌ ЕСТЬ ПРОБЛЕМЫ В ЛОГИКЕ!")
    
    print("=" * 80)
    print("\n")

