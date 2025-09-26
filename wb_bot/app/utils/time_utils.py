"""
Утилиты для работы со временем и проверки временных окон.
"""

from datetime import datetime, time
import pytz
from typing import Tuple, Optional

def is_within_time_window() -> Tuple[bool, Optional[str]]:
    """
    Проверяет, находимся ли мы в разрешенном временном окне для работы.
    
    Разрешенные окна (по Московскому времени):
    - 8:55 - 9:10
    - 9:55 - 10:10
    
    Returns:
        Tuple[bool, Optional[str]]: (в_окне, сообщение)
    """
    # Получаем текущее время по Москве
    moscow_tz = pytz.timezone('Europe/Moscow')
    current_time = datetime.now(moscow_tz).time()
    
    # Определяем временные окна
    windows = [
        (time(8, 55), time(9, 10), "8:55-9:10"),
        (time(9, 55), time(10, 10), "9:55-10:10")
    ]
    
    # Проверяем каждое окно
    for start, end, window_name in windows:
        if start <= current_time <= end:
            return True, f"Работаем в окне {window_name} МСК"
    
    # Если не в окне, определяем следующее окно
    current_minutes = current_time.hour * 60 + current_time.minute
    
    next_window = None
    min_diff = float('inf')
    
    for start, end, window_name in windows:
        start_minutes = start.hour * 60 + start.minute
        
        # Если окно еще не началось сегодня
        if start_minutes > current_minutes:
            diff = start_minutes - current_minutes
            if diff < min_diff:
                min_diff = diff
                next_window = (window_name, diff)
    
    # Если все окна прошли, следующее окно завтра
    if next_window is None:
        # До первого окна завтра
        tomorrow_start = windows[0][0]
        minutes_until_midnight = (24 * 60) - current_minutes
        minutes_after_midnight = tomorrow_start.hour * 60 + tomorrow_start.minute
        min_diff = minutes_until_midnight + minutes_after_midnight
        next_window = (windows[0][2], min_diff)
    
    window_name, minutes_until = next_window
    hours = minutes_until // 60
    minutes = minutes_until % 60
    
    if hours > 0:
        time_str = f"{hours}ч {minutes}мин"
    else:
        time_str = f"{minutes}мин"
    
    return False, f"Следующее окно {window_name} МСК через {time_str}"


def get_minutes_until_next_window() -> int:
    """
    Возвращает количество минут до следующего временного окна.
    
    Returns:
        int: Минуты до следующего окна
    """
    moscow_tz = pytz.timezone('Europe/Moscow')
    current_time = datetime.now(moscow_tz).time()
    current_minutes = current_time.hour * 60 + current_time.minute
    
    windows = [
        (time(8, 55), time(9, 10)),
        (time(9, 55), time(10, 10))
    ]
    
    min_wait = float('inf')
    
    for start, end in windows:
        start_minutes = start.hour * 60 + start.minute
        
        if start_minutes > current_minutes:
            wait = start_minutes - current_minutes
            min_wait = min(min_wait, wait)
    
    # Если все окна прошли, ждем до завтра
    if min_wait == float('inf'):
        tomorrow_start = windows[0][0]
        minutes_until_midnight = (24 * 60) - current_minutes
        minutes_after_midnight = tomorrow_start.hour * 60 + tomorrow_start.minute
        min_wait = minutes_until_midnight + minutes_after_midnight
    
    return int(min_wait)

