#!/usr/bin/env python3
"""
Тестовый скрипт для проверки очистки дублированных ошибок.
"""

def test_error_cleanup():
    """Тестируем логику очистки ошибок."""
    
    # Исходные ошибки (как их находит система)
    raw_errors = [
        "Дневной лимит исчерпан. Переместите товар с другого склада или попробуйте завтра",
        "Откуда забратьДневной лимит исчерпан. Переместите товар с другого склада или попробуйте завтра"
    ]
    
    print("🔍 Тестируем очистку ошибок:")
    print(f"Исходные ошибки: {len(raw_errors)}")
    for i, error in enumerate(raw_errors, 1):
        print(f"  {i}. '{error}'")
    
    # Применяем логику очистки
    error_messages = []
    
    for cleaned_error in raw_errors:
        # Очищаем ошибку от лишнего текста
        clean_patterns = [
            "откуда забрать",
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
        
        print(f"\n🧹 Очищенная ошибка: '{final_error}'")
        
        # Проверяем что ошибка не пустая и не слишком короткая
        if final_error and len(final_error) > 15:
            # Избегаем дублирования похожих ошибок
            is_duplicate = False
            for existing_error in error_messages:
                # Если новая ошибка содержится в существующей или наоборот
                if final_error in existing_error or existing_error in final_error:
                    is_duplicate = True
                    print(f"  ⚠️ Дубликат найден с: '{existing_error}'")
                    break
            
            if not is_duplicate:
                error_messages.append(final_error)
                print(f"  ✅ Добавлена уникальная ошибка")
            else:
                print(f"  ❌ Пропущен дубликат")
    
    print(f"\n🎯 РЕЗУЛЬТАТ:")
    print(f"Финальных ошибок: {len(error_messages)}")
    for i, error in enumerate(error_messages, 1):
        print(f"  {i}. '{error}'")
    
    # Ожидаемый результат: 1 ошибка
    if len(error_messages) == 1:
        print("✅ ТЕСТ ПРОШЕЛ: Остается только одна уникальная ошибка")
    else:
        print("❌ ТЕСТ НЕ ПРОШЕЛ: Должна остаться только одна ошибка")

if __name__ == "__main__":
    test_error_cleanup()


