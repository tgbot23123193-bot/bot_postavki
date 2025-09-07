"""
Обработчики для настроек поставок
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from ...utils.logger import get_logger

logger = get_logger(__name__)
router = Router()


@router.callback_query(F.data == "supplies_settings")
async def show_supplies_settings(callback: CallbackQuery, state: FSMContext):
    """Показывает настройки поставок."""
    await callback.message.edit_text(
        f"⚙️ <b>Настройки поставок</b>\n\n"
        f"🔔 <b>Уведомления:</b> Включены\n"
        f"🤖 <b>Автобронирование:</b> Включено\n"
        f"⏰ <b>Интервал проверки:</b> 60 сек\n\n"
        f"Выберите настройку для изменения:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Переключить уведомления", callback_data="toggle_notifications")],
            [InlineKeyboardButton(text="🗑 Очистить все сессии", callback_data="clear_all_sessions")],
            [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
        ])
    )


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    """Переключает уведомления."""
    await callback.message.edit_text(
        f"🔔 <b>Уведомления отключены</b>\n\n"
        f"❌ Уведомления о новых слотах: отключены\n"
        f"❌ Уведомления об успешном бронировании: отключены\n"
        f"❌ Уведомления об ошибках: отключены\n\n"
        f"<i>Функция в разработке - будет сохраняться в базу данных</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="supplies_settings")]
        ])
    )


@router.callback_query(F.data == "clear_all_sessions")
async def clear_all_sessions(callback: CallbackQuery):
    """Очищает все активные сессии."""
    user_id = callback.from_user.id
    
    try:
        # Импортируем сессии из booking_management
        from .booking_management import booking_browser_sessions, monitoring_sessions
        
        cleared_count = 0
        
        # Останавливаем автобронирование
        if user_id in booking_browser_sessions:
            session = booking_browser_sessions[user_id]
            session["status"] = "stopped"
            try:
                await session["browser"].close_browser()
            except:
                pass
            del booking_browser_sessions[user_id]
            cleared_count += 1
        
        # Останавливаем мониторинг
        if user_id in monitoring_sessions:
            session = monitoring_sessions[user_id]
            session["status"] = "stopped"
            del monitoring_sessions[user_id]
            cleared_count += 1
        
        await callback.message.edit_text(
            f"✅ <b>Сессии очищены</b>\n\n"
            f"🗑 Остановлено сессий: {cleared_count}\n"
            f"✅ Все процессы автобронирования и мониторинга остановлены\n\n"
            f"Теперь можете запустить новые сессии.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 К поставкам", callback_data="view_supplies")],
                [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="supplies_settings")]
            ])
        )
    except Exception as e:
        logger.error(f"❌ Ошибка очистки сессий: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка очистки сессий</b>\n\n"
            f"Не удалось очистить сессии: {e}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="supplies_settings")]
            ])
        )
