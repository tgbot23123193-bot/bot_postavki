"""
FSM states for bot conversation flows.

This module defines all conversation states for complex bot interactions
like creating monitoring tasks, adding API keys, etc.
"""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """States for user registration flow."""
    waiting_for_agreement = State()
    waiting_for_first_api_key = State()


class APIKeyStates(StatesGroup):
    """States for API key management."""
    waiting_for_api_key = State()
    waiting_for_key_name = State()
    waiting_for_key_description = State()
    waiting_for_rename = State()


class MonitoringStates(StatesGroup):
    """States for monitoring task creation and management."""
    waiting_for_warehouse_selection = State()
    waiting_for_date_range = State()
    waiting_for_supply_type = State()
    waiting_for_delivery_type = State()
    waiting_for_monitoring_mode = State()
    waiting_for_check_interval = State()
    waiting_for_max_coefficient = State()
    waiting_for_confirmation = State()
    
    # Edit states
    editing_warehouse = State()
    editing_dates = State()
    editing_supply_type = State()
    editing_delivery_type = State()
    editing_mode = State()
    editing_interval = State()
    editing_coefficient = State()


class SettingsStates(StatesGroup):
    """States for user settings management."""
    waiting_for_default_interval = State()
    waiting_for_default_coefficient = State()
    waiting_for_default_supply_type = State()
    waiting_for_default_delivery_type = State()
    waiting_for_default_mode = State()


class BookingStates(StatesGroup):
    """States for booking flow."""
    # Manual booking states
    waiting_for_warehouse = State()
    waiting_for_date = State()
    waiting_for_slot = State()
    waiting_for_supply_type = State()
    waiting_for_delivery_type = State()
    waiting_for_confirmation = State()
    
    # Auto booking states
    selecting_warehouse = State()
    selecting_dates = State()
    selecting_coefficient = State()
    selecting_interval = State()
    
    # Supply auto-booking states
    selecting_supply = State()
    selecting_start_date = State()
    selecting_end_date = State()
    confirming_dates = State()
    monitoring_slots = State()


class SupportStates(StatesGroup):
    """States for support and feedback."""
    waiting_for_message = State()
    waiting_for_feedback = State()


class AdminStates(StatesGroup):
    """States for admin operations."""
    waiting_for_broadcast_message = State()
    waiting_for_user_id = State()
    waiting_for_admin_command = State()
