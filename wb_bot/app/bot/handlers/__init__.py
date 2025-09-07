"""Handlers package initialization."""

from .base import router as base_router
from .api_keys import router as api_keys_router
from .monitoring import router as monitoring_router
from .monitoring_simple import router as monitoring_simple_router
from .callbacks import router as callbacks_router
from .booking import router as booking_router
from .browser_booking import router as browser_booking_router
from .supplies_management import router as supplies_management_router
from .booking_management import router as booking_management_router
from .supplies_settings import router as supplies_settings_router

# Export all routers
# ВАЖНО: callbacks_router должен быть ПЕРВЫМ для корректной работы FSM!
routers = [
    callbacks_router,
    booking_router,  # Автобронирование
    browser_booking_router,  # Браузерное бронирование
    supplies_management_router,  # Управление поставками
    booking_management_router,  # Бронирование поставок
    supplies_settings_router,  # Настройки поставок
    monitoring_simple_router,  # Простой мониторинг (быстрый поиск)
    base_router,
    api_keys_router,
    monitoring_router,
]

__all__ = ["routers"]
