"""
Additional inline keyboards for redistribution functionality.
"""

from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class RedistributionCallback(CallbackData, prefix="redistrib"):
    """Callback data for redistribution actions."""
    action: str  # start, cancel, back


class WarehouseCallback(CallbackData, prefix="warehouse"):
    """Callback data for warehouse selection."""
    action: str  # source, destination, select
    warehouse_id: str


def get_redistribution_menu() -> InlineKeyboardMarkup:
    """
    Get redistribution menu keyboard.
    
    Returns:
        Redistribution menu keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🚀 Начать перераспределение",
                callback_data=RedistributionCallback(action="start").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Активные задачи (до 3)",
                callback_data="show_active_tasks"
            )
        ],
        [
            InlineKeyboardButton(
                text="🚀 Открыть страницу перераспределения",
                callback_data="open_redistribution_page"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Инструкция",
                callback_data="redistribution_instructions"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="main_menu"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_warehouses_keyboard(warehouses: List[dict], action: str = "source") -> InlineKeyboardMarkup:
    """
    Create keyboard with warehouse buttons.
    
    Args:
        warehouses: List of warehouse dictionaries
        action: Action type ("source" or "destination")
        
    Returns:
        Keyboard with warehouse buttons
    """
    keyboard = []
    
    for warehouse in warehouses:
        warehouse_name = warehouse.get('name', 'Неизвестный склад')
        warehouse_id = warehouse.get('id', '')
        quantity = warehouse.get('quantity', 0)
        
        # Добавляем количество к названию склада
        quantity_full = warehouse.get('quantity_full', 0)
        
        if quantity_full > quantity:
            button_text = f"🏪 {warehouse_name} ({quantity}+{quantity_full-quantity} шт)"
        else:
            button_text = f"🏪 {warehouse_name} ({quantity} шт)"
        
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=WarehouseCallback(action=action, warehouse_id=warehouse_id).pack()
            )
        ])
    
    # Добавляем кнопку отмены
    keyboard.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="redistribution_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
