"""
Конфигурация для процесса распределения.
"""

import os
from typing import List, Tuple
from datetime import time

class RedistributionConfig:
    """Настройки для процесса распределения."""
    
    @staticmethod
    def get_booking_periods() -> List[Tuple[time, time]]:
        """
        Получает периоды для активного бронирования из ENV.
        
        Returns:
            List[Tuple[time, time]]: Список периодов (начало, конец)
        """
        periods_str = os.getenv('REDISTRIBUTION_BOOKING_PERIODS', '8:55-9:10,9:55-10:10')
        periods = []
        
        for period in periods_str.split(','):
            if '-' in period:
                start_str, end_str = period.strip().split('-')
                start_h, start_m = map(int, start_str.split(':'))
                end_h, end_m = map(int, end_str.split(':'))
                periods.append((time(start_h, start_m), time(end_h, end_m)))
        
        return periods
    
    @staticmethod
    def get_retry_minutes() -> int:
        """Получает время ожидания между попытками ВНЕ активных периодов в минутах."""
        return int(os.getenv('REDISTRIBUTION_RETRY_MINUTES', '31'))
    
    @staticmethod
    def get_active_retry_minutes() -> int:
        """Получает время ожидания между попытками В активных периодах в минутах."""
        return int(os.getenv('REDISTRIBUTION_ACTIVE_RETRY_MINUTES', '1'))
    
    @staticmethod
    def is_auto_retry_enabled() -> bool:
        """Проверяет, включен ли автоматический повтор."""
        return os.getenv('REDISTRIBUTION_AUTO_RETRY', 'true').lower() == 'true'
    
    @staticmethod
    def get_max_attempts() -> int:
        """Получает максимальное количество попыток."""
        return int(os.getenv('REDISTRIBUTION_MAX_ATTEMPTS', '100'))
    
    @staticmethod
    def is_in_booking_period() -> bool:
        """
        Проверяет, находимся ли мы в одном из активных периодов бронирования.
        
        Returns:
            bool: True если в активном периоде, False если нет
        """
        from datetime import datetime
        import pytz
        
        # Получаем текущее время по Москве
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz).time()
        
        # Проверяем каждый период
        for start, end in RedistributionConfig.get_booking_periods():
            if start <= current_time <= end:
                return True
        
        return False
    
    @staticmethod
    def minutes_until_next_period() -> int:
        """
        Возвращает количество минут до следующего активного периода.
        
        Returns:
            int: Минуты до следующего периода
        """
        from datetime import datetime
        import pytz
        
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz).time()
        current_minutes = current_time.hour * 60 + current_time.minute
        
        min_wait = float('inf')
        
        for start, end in RedistributionConfig.get_booking_periods():
            start_minutes = start.hour * 60 + start.minute
            
            if start_minutes > current_minutes:
                wait = start_minutes - current_minutes
                min_wait = min(min_wait, wait)
        
        # Если все периоды прошли, ждем до завтра
        if min_wait == float('inf'):
            periods = RedistributionConfig.get_booking_periods()
            if periods:
                tomorrow_start = periods[0][0]
                minutes_until_midnight = (24 * 60) - current_minutes
                minutes_after_midnight = tomorrow_start.hour * 60 + tomorrow_start.minute
                min_wait = minutes_until_midnight + minutes_after_midnight
        
        return int(min_wait)
    
    @staticmethod
    def get_current_retry_interval() -> int:
        """
        Возвращает текущий интервал повтора в зависимости от времени.
        
        Returns:
            int: Интервал в минутах (1 в активные периоды, 31 вне периодов)
        """
        if RedistributionConfig.is_in_booking_period():
            return RedistributionConfig.get_active_retry_minutes()  # 1 минута в активные периоды
        else:
            return RedistributionConfig.get_retry_minutes()  # 31 минута вне периодов
