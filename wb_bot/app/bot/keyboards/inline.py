"""
Inline keyboards for bot interface.

This module provides all inline keyboards for the bot's user interface
with proper callback handling and responsive design.
"""

from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

from ...database.models import MonitoringTask, APIKey, SupplyType, DeliveryType, MonitoringMode


class RedistributionCallback(CallbackData, prefix="redistrib"):
    """Callback data for redistribution actions."""
    action: str  # start, cancel, back


class WarehouseCallback(CallbackData, prefix="warehouse"):
    """Callback data for warehouse selection."""
    action: str  # source, destination, select
    warehouse_id: str


class MainMenuCallback(CallbackData, prefix="main"):
    """Main menu callback data."""
    action: str  # monitoring, api_keys, settings, help, stats


class MonitoringCallback(CallbackData, prefix="monitor"):
    """Monitoring callback data."""
    action: str  # create, list, edit, delete, pause, resume
    task_id: int = 0


class APIKeyCallback(CallbackData, prefix="apikey"):
    """API key callback data."""
    action: str  # add, list, delete, validate, confirm_delete
    key_id: int = 0


class SettingsCallback(CallbackData, prefix="settings"):
    """Settings callback data."""
    action: str  # interval, coefficient, supply_type, delivery_type, mode
    value: str = ""


def get_main_menu() -> InlineKeyboardMarkup:
    """
    Get main menu keyboard.
    
    Returns:
        Main menu keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 Мониторинг слотов",
                callback_data=MainMenuCallback(action="monitoring").pack()
            ),
            InlineKeyboardButton(
                text="🤖 Автобронирование",
                callback_data="auto_booking"
            )
        ],
        [
            InlineKeyboardButton(
                text="📦 Управление поставками",
                callback_data="view_supplies"
            ),
            InlineKeyboardButton(
                text="🔄 Перераспределение остатков",
                callback_data="redistribution_menu"
            )
        ],
        [
            InlineKeyboardButton(
                text="💰 Баланс",
                callback_data="wallet_main"
            ),
            InlineKeyboardButton(
                text="🔑 API ключи",
                callback_data=MainMenuCallback(action="api_keys").pack()
            ),
        ],
        [
            InlineKeyboardButton(
                text="❓ Помощь",
                callback_data=MainMenuCallback(action="help").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_menu() -> InlineKeyboardMarkup:
    """
    Get monitoring menu keyboard.
    
    Returns:
        Monitoring menu keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="➕ Создать мониторинг",
                callback_data=MonitoringCallback(action="create").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Мои мониторинги",
                callback_data=MonitoringCallback(action="list").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Главное меню",
                callback_data=MainMenuCallback(action="main").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_list_keyboard(tasks: List[MonitoringTask]) -> InlineKeyboardMarkup:
    """
    Get keyboard for monitoring tasks list.
    
    Args:
        tasks: List of monitoring tasks
        
    Returns:
        Keyboard with task list
    """
    keyboard = []
    
    for task in tasks:
        status_emoji = "🟢" if task.is_active and not task.is_paused else "🔴" if task.is_paused else "⚪"
        mode_emoji = "🤖" if task.monitoring_mode == "auto_booking" else "🔔"
        
        task_text = (f"{status_emoji}{mode_emoji} {task.warehouse_name} "
                    f"({task.date_from.strftime('%d.%m')} - {task.date_to.strftime('%d.%m')})")
        
        keyboard.append([
            InlineKeyboardButton(
                text=task_text,
                callback_data=MonitoringCallback(action="edit", task_id=task.id).pack()
            )
        ])
    
    # Navigation buttons
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=MonitoringCallback(action="back").pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_task_keyboard(task: MonitoringTask) -> InlineKeyboardMarkup:
    """
    Get keyboard for individual monitoring task.
    
    Args:
        task: Monitoring task
        
    Returns:
        Task management keyboard
    """
    keyboard = []
    
    # Pause/Resume button
    if task.is_active and not task.is_paused:
        keyboard.append([
            InlineKeyboardButton(
                text="⏸ Приостановить",
                callback_data=MonitoringCallback(action="pause", task_id=task.id).pack()
            )
        ])
    elif task.is_paused:
        keyboard.append([
            InlineKeyboardButton(
                text="▶️ Возобновить",
                callback_data=MonitoringCallback(action="resume", task_id=task.id).pack()
            )
        ])
    
    # Edit and delete buttons
    keyboard.append([
        InlineKeyboardButton(
            text="✏️ Изменить",
            callback_data=MonitoringCallback(action="edit_settings", task_id=task.id).pack()
        ),
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=MonitoringCallback(action="delete", task_id=task.id).pack()
        )
    ])
    
    # Back button
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 К списку",
            callback_data=MonitoringCallback(action="list").pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_api_keys_menu() -> InlineKeyboardMarkup:
    """
    Get API keys menu keyboard.
    
    Returns:
        API keys menu keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="➕ Добавить API ключ",
                callback_data=APIKeyCallback(action="add").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Мои ключи",
                callback_data=APIKeyCallback(action="list").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🔍 Проверить ключи",
                callback_data=APIKeyCallback(action="validate").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Главное меню",
                callback_data=MainMenuCallback(action="main").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_api_keys_list_keyboard(api_keys: List[APIKey]) -> InlineKeyboardMarkup:
    """
    Get keyboard for API keys list.
    
    Args:
        api_keys: List of API keys
        
    Returns:
        Keyboard with API keys list
    """
    keyboard = []
    
    for api_key in api_keys:
        status_emoji = "🟢" if api_key.is_valid else "🔴"
        key_text = f"{status_emoji} {api_key.name} ({api_key.created_at.strftime('%d.%m.%Y')})"
        
        keyboard.append([
            InlineKeyboardButton(
                text=key_text,
                callback_data=APIKeyCallback(action="manage", key_id=api_key.id).pack()
            )
        ])
    
    # Navigation buttons
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=APIKeyCallback(action="back").pack()
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_api_key_management_keyboard(api_key: APIKey) -> InlineKeyboardMarkup:
    """
    Get keyboard for managing individual API key.
    
    Args:
        api_key: API key to manage
        
    Returns:
        API key management keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔍 Проверить",
                callback_data=APIKeyCallback(action="test", key_id=api_key.id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Переименовать",
                callback_data=APIKeyCallback(action="rename", key_id=api_key.id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=APIKeyCallback(action="delete", key_id=api_key.id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 К списку",
                callback_data=APIKeyCallback(action="list").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_supply_type_keyboard() -> InlineKeyboardMarkup:
    """Get supply type selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📦 Короб",
                callback_data=SettingsCallback(action="supply_type", value="box").pack()
            ),
            InlineKeyboardButton(
                text="🏗 Монопаллета",
                callback_data=SettingsCallback(action="supply_type", value="mono_pallet").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_delivery_type_keyboard() -> InlineKeyboardMarkup:
    """Get delivery type selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🚚 Прямая",
                callback_data=SettingsCallback(action="delivery_type", value="direct").pack()
            ),
            InlineKeyboardButton(
                text="🔄 Транзитная",
                callback_data=SettingsCallback(action="delivery_type", value="transit").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_monitoring_mode_keyboard() -> InlineKeyboardMarkup:
    """Get monitoring mode selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔔 Только уведомления",
                callback_data=SettingsCallback(action="mode", value="notification").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🤖 Автобронирование",
                callback_data=SettingsCallback(action="mode", value="auto_booking").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_coefficient_keyboard() -> InlineKeyboardMarkup:
    """Get coefficient selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="1.0x",
                callback_data=SettingsCallback(action="coefficient", value="1.0").pack()
            ),
            InlineKeyboardButton(
                text="2.0x",
                callback_data=SettingsCallback(action="coefficient", value="2.0").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="3.0x",
                callback_data=SettingsCallback(action="coefficient", value="3.0").pack()
            ),
            InlineKeyboardButton(
                text="5.0x",
                callback_data=SettingsCallback(action="coefficient", value="5.0").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_check_interval_keyboard() -> InlineKeyboardMarkup:
    """Get check interval selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="30 сек",
                callback_data=SettingsCallback(action="interval", value="30").pack()
            ),
            InlineKeyboardButton(
                text="1 мин",
                callback_data=SettingsCallback(action="interval", value="60").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="5 мин",
                callback_data=SettingsCallback(action="interval", value="300").pack()
            ),
            InlineKeyboardButton(
                text="10 мин",
                callback_data=SettingsCallback(action="interval", value="600").pack()
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(action: str, item_id: int = 0) -> InlineKeyboardMarkup:
    """
    Get confirmation keyboard for dangerous actions.
    
    Args:
        action: Action to confirm
        item_id: Item ID for the action
        
    Returns:
        Confirmation keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Да, подтвердить",
                callback_data=f"confirm_{action}_{item_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Нет, отменить",
                callback_data=f"cancel_{action}"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """
    Get pagination keyboard.
    
    Args:
        current_page: Current page number (0-based)
        total_pages: Total number of pages
        callback_prefix: Prefix for callback data
        
    Returns:
        Pagination keyboard
    """
    keyboard = []
    
    if total_pages > 1:
        row = []
        
        if current_page > 0:
            row.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"{callback_prefix}_page_{current_page - 1}"
                )
            )
        
        row.append(
            InlineKeyboardButton(
                text=f"{current_page + 1}/{total_pages}",
                callback_data="ignore"
            )
        )
        
        if current_page < total_pages - 1:
            row.append(
                InlineKeyboardButton(
                    text="Вперед ▶️",
                    callback_data=f"{callback_prefix}_page_{current_page + 1}"
                )
            )
        
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_button(callback_data: str) -> InlineKeyboardMarkup:
    """
    Get simple back button keyboard.
    
    Args:
        callback_data: Callback data for back button
        
    Returns:
        Back button keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=callback_data
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Get back to main menu keyboard.
    
    Returns:
        Back to main menu keyboard
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="⬅️ Главное меню",
                callback_data="main_menu"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
