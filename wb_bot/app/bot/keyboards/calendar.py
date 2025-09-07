"""
Interactive calendar keyboard for date range selection.

This module provides a professional calendar interface for selecting
date ranges with navigation and proper validation.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from pydantic import BaseModel

from ...utils.logger import get_logger

logger = get_logger(__name__)


class CalendarCallback(CallbackData, prefix="cal"):
    """Callback data for calendar interactions."""
    action: str  # nav_prev, nav_next, select, confirm
    year: int
    month: int
    day: int = 0  # 0 for navigation actions


class DateSelection(BaseModel):
    """Model for tracking date selection state."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    current_year: int
    current_month: int
    selecting_start: bool = True  # True for start date, False for end date


class DateRangeCalendar:
    """
    Interactive calendar for date range selection.
    
    Features:
    - Month navigation with arrows
    - Start and end date selection
    - Visual feedback for selected dates
    - Proper validation (end date >= start date)
    - Responsive layout optimized for Telegram
    """
    
    # Calendar configuration
    MONTHS_RU = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    # Emoji for visual enhancement
    EMOJI_SELECTED_START = "🟩"  # Start date
    EMOJI_SELECTED_END = "🟥"    # End date
    EMOJI_IN_RANGE = "🟨"        # Dates in range
    EMOJI_TODAY = "📅"           # Today
    EMOJI_PREV = "◀️"            # Previous month
    EMOJI_NEXT = "▶️"            # Next month
    EMOJI_CONFIRM = "✅"         # Confirm selection
    EMOJI_CANCEL = "❌"          # Cancel
    
    def __init__(self):
        """Initialize calendar."""
        self.selections: Dict[int, DateSelection] = {}  # user_id -> DateSelection
    
    def get_calendar_keyboard(
        self,
        user_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        min_date: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Generate calendar keyboard for date selection.
        
        Args:
            user_id: User ID for state tracking
            year: Year to display (default: current year)
            month: Month to display (default: current month)
            
        Returns:
            InlineKeyboardMarkup with calendar
        """
        today = date.today()
        year = year or today.year
        month = month or today.month
        
        # Initialize or update selection state
        if user_id not in self.selections:
            self.selections[user_id] = DateSelection(
                current_year=year,
                current_month=month
            )
        else:
            self.selections[user_id].current_year = year
            self.selections[user_id].current_month = month
        
        selection = self.selections[user_id]
        
        # Create keyboard
        keyboard = []
        
        # Header with month/year and navigation
        header_row = [
            InlineKeyboardButton(
                text=f"{self.EMOJI_PREV}",
                callback_data=CalendarCallback(
                    action="nav_prev",
                    year=year,
                    month=month
                ).pack()
            ),
            InlineKeyboardButton(
                text=f"{self.MONTHS_RU[month-1]} {year}",
                callback_data="ignore"
            ),
            InlineKeyboardButton(
                text=f"{self.EMOJI_NEXT}",
                callback_data=CalendarCallback(
                    action="nav_next",
                    year=year,
                    month=month
                ).pack()
            )
        ]
        keyboard.append(header_row)
        
        # Weekday headers
        weekday_row = [
            InlineKeyboardButton(text=day, callback_data="ignore")
            for day in self.WEEKDAYS_RU
        ]
        keyboard.append(weekday_row)
        
        # Calendar days
        cal = calendar.monthcalendar(year, month)
        
        for week in cal:
            week_row = []
            for day in week:
                if day == 0:
                    # Empty cell for days from other months
                    week_row.append(
                        InlineKeyboardButton(text=" ", callback_data="ignore")
                    )
                else:
                    current_date = date(year, month, day)
                    
                    # Determine button appearance
                    text = str(day)
                    
                    # Check if this date is selected
                    if selection.start_date == current_date:
                        text = f"{self.EMOJI_SELECTED_START}{day}"
                    elif selection.end_date == current_date:
                        text = f"{self.EMOJI_SELECTED_END}{day}"
                    elif (selection.start_date and selection.end_date and
                          selection.start_date < current_date < selection.end_date):
                        text = f"{self.EMOJI_IN_RANGE}{day}"
                    elif current_date == today:
                        text = f"{self.EMOJI_TODAY}{day}"
                    
                    # Disable past dates
                    if current_date < today:
                        week_row.append(
                            InlineKeyboardButton(text=f"·{day}·", callback_data="ignore")
                        )
                    else:
                        week_row.append(
                            InlineKeyboardButton(
                                text=text,
                                callback_data=CalendarCallback(
                                    action="select",
                                    year=year,
                                    month=month,
                                    day=day
                                ).pack()
                            )
                        )
            
            keyboard.append(week_row)
        
        # Status and action buttons
        status_text = self._get_status_text(selection)
        keyboard.append([
            InlineKeyboardButton(text=status_text, callback_data="ignore")
        ])
        
        # Action buttons
        action_row = []
        
        if selection.start_date and selection.end_date:
            action_row.append(
                InlineKeyboardButton(
                    text=f"{self.EMOJI_CONFIRM} Подтвердить",
                    callback_data=CalendarCallback(
                        action="confirm",
                        year=year,
                        month=month
                    ).pack()
                )
            )
        
        action_row.append(
            InlineKeyboardButton(
                text=f"{self.EMOJI_CANCEL} Отмена",
                callback_data=CalendarCallback(
                    action="cancel",
                    year=year,
                    month=month
                ).pack()
            )
        )
        
        if action_row:
            keyboard.append(action_row)
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def _get_status_text(self, selection: DateSelection) -> str:
        """Get status text for current selection."""
        if not selection.start_date:
            return "📅 Выберите начальную дату"
        elif not selection.end_date:
            return f"📅 Начало: {selection.start_date.strftime('%d.%m.%Y')}\n📅 Выберите конечную дату"
        else:
            days_diff = (selection.end_date - selection.start_date).days + 1
            return (f"📅 Период: {selection.start_date.strftime('%d.%m.%Y')} - "
                   f"{selection.end_date.strftime('%d.%m.%Y')} ({days_diff} дн.)")
    
    def handle_calendar_callback(
        self,
        user_id: int,
        callback_data: CalendarCallback
    ) -> Tuple[str, Optional[InlineKeyboardMarkup], Optional[Tuple[date, date]]]:
        """
        Handle calendar callback and return updated state.
        
        Args:
            user_id: User ID
            callback_data: Parsed callback data
            
        Returns:
            Tuple of (action_result, updated_keyboard, selected_dates)
            - action_result: Description of what happened
            - updated_keyboard: New keyboard or None if no update needed
            - selected_dates: (start_date, end_date) if confirmed, None otherwise
        """
        if user_id not in self.selections:
            return "Ошибка: состояние календаря не найдено", None, None
        
        selection = self.selections[user_id]
        action = callback_data.action
        
        if action == "nav_prev":
            # Navigate to previous month
            year, month = callback_data.year, callback_data.month
            if month == 1:
                month = 12
                year -= 1
            else:
                month -= 1
            
            new_keyboard = self.get_calendar_keyboard(user_id, year, month)
            return "Переход к предыдущему месяцу", new_keyboard, None
        
        elif action == "nav_next":
            # Navigate to next month
            year, month = callback_data.year, callback_data.month
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
            
            new_keyboard = self.get_calendar_keyboard(user_id, year, month)
            return "Переход к следующему месяцу", new_keyboard, None
        
        elif action == "select":
            # Select a date
            selected_date = date(callback_data.year, callback_data.month, callback_data.day)
            
            if not selection.start_date:
                # Selecting start date
                selection.start_date = selected_date
                selection.selecting_start = False
                new_keyboard = self.get_calendar_keyboard(
                    user_id, callback_data.year, callback_data.month
                )
                return f"Начальная дата выбрана: {selected_date.strftime('%d.%m.%Y')}", new_keyboard, None
            
            elif not selection.end_date:
                # Selecting end date
                if selected_date < selection.start_date:
                    # If selected date is before start date, make it the new start date
                    selection.end_date = selection.start_date
                    selection.start_date = selected_date
                else:
                    selection.end_date = selected_date
                
                new_keyboard = self.get_calendar_keyboard(
                    user_id, callback_data.year, callback_data.month
                )
                return f"Конечная дата выбрана: {selected_date.strftime('%d.%m.%Y')}", new_keyboard, None
            
            else:
                # Both dates already selected, reset and select new start date
                selection.start_date = selected_date
                selection.end_date = None
                selection.selecting_start = False
                new_keyboard = self.get_calendar_keyboard(
                    user_id, callback_data.year, callback_data.month
                )
                return f"Новая начальная дата: {selected_date.strftime('%d.%m.%Y')}", new_keyboard, None
        
        elif action == "confirm":
            # Confirm selection
            if selection.start_date and selection.end_date:
                result_dates = (selection.start_date, selection.end_date)
                # Clear selection for this user
                del self.selections[user_id]
                return "Период выбран успешно!", None, result_dates
            else:
                return "Ошибка: не все даты выбраны", None, None
        
        elif action == "cancel":
            # Cancel selection
            if user_id in self.selections:
                del self.selections[user_id]
            return "Выбор дат отменен", None, None
        
        return "Неизвестное действие", None, None
    
    def get_selection_state(self, user_id: int) -> Optional[DateSelection]:
        """Get current selection state for user."""
        return self.selections.get(user_id)
    
    def clear_selection(self, user_id: int) -> None:
        """Clear selection state for user."""
        if user_id in self.selections:
            del self.selections[user_id]
    
    def validate_date_range(self, start_date: date, end_date: date) -> Tuple[bool, str]:
        """
        Validate selected date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        today = date.today()
        
        if start_date < today:
            return False, "Начальная дата не может быть в прошлом"
        
        if end_date < start_date:
            return False, "Конечная дата не может быть раньше начальной"
        
        # Check if range is too long (e.g., max 90 days)
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return False, "Период не может превышать 90 дней"
        
        # Check if range is too far in the future (e.g., max 1 year)
        max_future_date = today + timedelta(days=365)
        if end_date > max_future_date:
            return False, "Дата не может быть более чем на год вперед"
        
        return True, ""


# Global calendar instance
date_calendar = DateRangeCalendar()


def get_date_range_calendar(user_id: int) -> InlineKeyboardMarkup:
    """
    Get calendar keyboard for date range selection.
    
    Args:
        user_id: User ID
        
    Returns:
        Calendar keyboard
    """
    return date_calendar.get_calendar_keyboard(user_id)


def handle_calendar_callback(
    user_id: int,
    callback_data: CalendarCallback
) -> Tuple[str, Optional[InlineKeyboardMarkup], Optional[Tuple[date, date]]]:
    """
    Handle calendar callback.
    
    Args:
        user_id: User ID
        callback_data: Calendar callback data
        
    Returns:
        Tuple of (message, keyboard, dates)
    """
    return date_calendar.handle_calendar_callback(user_id, callback_data)
