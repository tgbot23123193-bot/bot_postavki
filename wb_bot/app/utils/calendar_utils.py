"""
Утилиты для создания интерактивного календаря в Telegram
"""
import calendar
from datetime import datetime, timedelta
from typing import List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class TelegramCalendar:
    """Класс для создания интерактивного календаря в Telegram"""
    
    # Названия месяцев на русском
    MONTHS = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    # Названия дней недели на русском (сокращенные)
    WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    @classmethod
    def create_calendar(cls, year: int = None, month: int = None, supply_id: str = "", preorder_id: str = "") -> InlineKeyboardMarkup:
        """
        Создает календарь для выбора даты
        
        Args:
            year: Год (по умолчанию текущий)
            month: Месяц (по умолчанию текущий)
            supply_id: ID поставки для callback данных
            preorder_id: ID предзаказа для callback данных
            
        Returns:
            InlineKeyboardMarkup с календарем
        """
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
            
        # Заголовок с месяцем и годом
        header = f"📅 {cls.MONTHS[month-1]} {year}"
        
        # Создаем календарь
        cal = calendar.monthcalendar(year, month)
        
        keyboard = []
        
        # Строка с заголовком
        keyboard.append([
            InlineKeyboardButton(
                text=header, 
                callback_data="calendar_ignore"
            )
        ])
        
        # Кнопки навигации по месяцам
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        
        keyboard.append([
            InlineKeyboardButton(
                text="◀️", 
                callback_data=f"calendar_nav_{prev_year}_{prev_month}_{supply_id}_{preorder_id}"
            ),
            InlineKeyboardButton(
                text="▶️", 
                callback_data=f"calendar_nav_{next_year}_{next_month}_{supply_id}_{preorder_id}"
            )
        ])
        
        # Строка с днями недели
        keyboard.append([
            InlineKeyboardButton(text=day, callback_data="calendar_ignore") 
            for day in cls.WEEKDAYS
        ])
        
        # Строки с датами
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        for week in cal:
            week_buttons = []
            for day in week:
                if day == 0:
                    # Пустые дни
                    week_buttons.append(
                        InlineKeyboardButton(text=" ", callback_data="calendar_ignore")
                    )
                else:
                    current_date = datetime(year, month, day).date()
                    
                    # Определяем доступность даты
                    if current_date < tomorrow:
                        # Прошедшие дни и сегодня - недоступны
                        week_buttons.append(
                            InlineKeyboardButton(
                                text=f"❌{day}", 
                                callback_data="calendar_ignore"
                            )
                        )
                    elif current_date == today:
                        # Сегодня - выделяем но недоступно
                        week_buttons.append(
                            InlineKeyboardButton(
                                text=f"🔴{day}", 
                                callback_data="calendar_ignore"
                            )
                        )
                    else:
                        # Доступные даты
                        date_str = current_date.strftime("%d.%m.%Y")
                        week_buttons.append(
                            InlineKeyboardButton(
                                text=str(day), 
                                callback_data=f"calendar_select_{date_str}_{supply_id}_{preorder_id}"
                            )
                        )
            
            keyboard.append(week_buttons)
        
        # Кнопка назад
        keyboard.append([
            InlineKeyboardButton(
                text="🔙 Назад к вариантам", 
                callback_data=f"browser_book_supply:{supply_id}"
            )
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @classmethod
    def get_calendar_text(cls, year: int, month: int) -> str:
        """
        Генерирует текст для сообщения с календарем
        
        Args:
            year: Год
            month: Месяц
            
        Returns:
            Текст для сообщения
        """
        return (
            f"📅 <b>ВЫБОР ДАТЫ БРОНИРОВАНИЯ</b>\n\n"
            f"🗓️ <b>{cls.MONTHS[month-1]} {year}</b>\n\n"
            f"✅ <b>Зеленые числа</b> - доступные даты\n"
            f"🔴 <b>Красные</b> - сегодня (недоступно)\n"
            f"❌ <b>Серые</b> - прошедшие дни\n\n"
            f"👆 <b>Нажмите на нужную дату</b>\n"
            f"◀️▶️ <b>Переключение месяцев</b>"
        )


def parse_calendar_callback(callback_data: str) -> Tuple[str, ...]:
    """
    Парсит callback_data от календаря
    
    Args:
        callback_data: Строка с данными callback
        
    Returns:
        Кортеж с типом действия и параметрами
    """
    parts = callback_data.split("_")
    if len(parts) < 2:
        return ("unknown",)
    
    action_type = parts[1]  # nav, select, ignore
    
    if action_type == "nav":
        # calendar_nav_2024_9_supply_preorder
        if len(parts) >= 6:
            return ("nav", int(parts[2]), int(parts[3]), parts[4], parts[5])
        return ("nav",)
    
    elif action_type == "select":
        # calendar_select_15.09.2024_supply_preorder
        if len(parts) >= 5:
            return ("select", parts[2], parts[3], parts[4])
        return ("select",)
    
    else:
        return ("ignore",)

