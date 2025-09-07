"""
General callback handlers for the bot.

This module contains handlers for various callback queries that don't
belong to specific modules like monitoring or API keys.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from ..keyboards.inline import MainMenuCallback, get_main_menu

router = Router()


@router.callback_query(MainMenuCallback.filter(F.action == "monitoring"))
async def show_monitoring_menu(callback: CallbackQuery):
    """Show monitoring main menu."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Мониторинг в разработке", callback_data="test_monitoring")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="test_back")]
        ])
        
        await callback.message.edit_text(
            "📊 <b>Мониторинг слотов</b>\n\n"
            "Управление мониторингом складских слотов Wildberries.\n"
            "Создавайте автоматические проверки и получайте уведомления "
            "о появлении подходящих слотов для поставок.\n\n"
            "⚠️ Функция временно недоступна",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "api_keys"))
async def show_api_keys_menu(callback: CallbackQuery):
    """Show API keys main menu."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить API ключ", callback_data="test_add_key")],
            [InlineKeyboardButton(text="📋 Мои ключи", callback_data="test_list_keys")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="test_back")]
        ])
        
        api_keys_text = (
            "🔑 <b>Управление API ключами</b>\n\n"
            "API ключи Wildberries необходимы для работы с системой поставок.\n"
            "Вы можете добавить до 5 ключей для распределения нагрузки.\n\n"
            "🔒 <b>Безопасность:</b> Все ключи шифруются и хранятся в защищенном виде.\n\n"
            "Выберите действие:"
        )
        
        await callback.message.edit_text(
            api_keys_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "settings"))
async def show_settings_menu(callback: CallbackQuery):
    """Show settings menu."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки временно недоступны", callback_data="test_settings")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="test_back")]
        ])
        
        await callback.message.edit_text(
            "⚙️ <b>Настройки</b>\n\n"
            "Настройки бота временно недоступны.\n"
            "Функция будет добавлена в следующих версиях.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "stats"))
async def show_detailed_stats(callback: CallbackQuery):
    """Show detailed user statistics."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="test_back")]
        ])
        
        stats_text = (
            "📊 <b>Статистика</b>\n\n"
            "📈 <b>Общая статистика:</b>\n"
            "• Активных мониторингов: 0\n"
            "• Успешных бронирований: 0\n"
            "• API ключей: 0\n"
            "• Дата регистрации: сегодня\n\n"
            "📊 Подробная статистика будет доступна после добавления API ключей."
        )
        
        await callback.message.edit_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "help"))
async def show_help_menu(callback: CallbackQuery):
    """Show help menu."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="test_back")]
        ])
        
        help_text = (
            "❓ <b>Справка по использованию</b>\n\n"
            "🔑 <b>API ключи:</b>\n"
            "Добавьте ваши API ключи Wildberries для работы с системой поставок.\n\n"
            "📊 <b>Мониторинг:</b>\n"
            "Настройте автоматическое отслеживание доступных слотов на складах.\n\n"
            "🤖 <b>Автобронирование:</b>\n"
            "Бот автоматически забронирует подходящие слоты при их появлении.\n\n"
            "📞 <b>Поддержка:</b>\n"
            "Если у вас есть вопросы, обратитесь к администратору."
        )
        
        await callback.message.edit_text(
            help_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# Тестовые обработчики для кнопок
@router.callback_query(F.data == "test_add_key")
async def test_add_key_handler(callback: CallbackQuery):
    """Тестовый обработчик добавления ключа."""
    await callback.answer("🔑 Функция добавления API ключа временно недоступна", show_alert=True)


@router.callback_query(F.data == "test_list_keys")
async def test_list_keys_handler(callback: CallbackQuery):
    """Тестовый обработчик списка ключей."""
    await callback.answer("📋 У вас пока нет API ключей", show_alert=True)


@router.callback_query(F.data == "test_settings")
async def test_settings_handler(callback: CallbackQuery):
    """Тестовый обработчик настроек."""
    await callback.answer("⚙️ Настройки в разработке", show_alert=True)


@router.callback_query(F.data == "test_monitoring")
async def test_monitoring_handler(callback: CallbackQuery):
    """Тестовый обработчик мониторинга."""
    await callback.answer("📊 Мониторинг в разработке", show_alert=True)


@router.callback_query(F.data == "test_back")
async def test_back_handler(callback: CallbackQuery):
    """Тестовый обработчик возврата."""
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Добро пожаловать в WB Auto-Booking Bot!\n"
        "Выберите нужную функцию:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()



