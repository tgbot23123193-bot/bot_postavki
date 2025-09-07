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
    from ..keyboards.inline import get_monitoring_menu
    
    await callback.message.edit_text(
        "📊 <b>Мониторинг слотов</b>\n\n"
        "Управление мониторингом складских слотов Wildberries.\n"
        "Создавайте автоматические проверки и получайте уведомления "
        "о появлении подходящих слотов для поставок.\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_monitoring_menu()
    )
    await callback.answer()


@router.callback_query(MainMenuCallback.filter(F.action == "api_keys"))
async def show_api_keys_menu(callback: CallbackQuery):
    """Show API keys main menu."""
    try:
        # Простое меню без базы данных
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
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


@router.callback_query(F.data == "test_add_key")
async def test_add_key_handler(callback: CallbackQuery):
    """Тестовый обработчик добавления ключа."""
    await callback.answer("🔑 Функция добавления API ключа временно недоступна", show_alert=True)


@router.callback_query(F.data == "test_list_keys")
async def test_list_keys_handler(callback: CallbackQuery):
    """Тестовый обработчик списка ключей."""
    await callback.answer("📋 У вас пока нет API ключей", show_alert=True)


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


@router.callback_query(MainMenuCallback.filter(F.action == "settings"))
async def show_settings_menu(callback: CallbackQuery):
    """Show settings menu."""
    try:
        # Простое меню настроек без базы данных
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
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


@router.callback_query(F.data == "test_settings")
async def test_settings_handler(callback: CallbackQuery):
    """Тестовый обработчик настроек."""
    await callback.answer("⚙️ Настройки в разработке", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "stats"))
async def show_detailed_stats(callback: CallbackQuery):
    """Show detailed user statistics."""
    try:
        # Простая статистика без базы данных
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
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
    
    # Calculate success rates
    booking_success_rate = 0
    if total_successful_bookings + total_failed_bookings > 0:
        booking_success_rate = (total_successful_bookings / (total_successful_bookings + total_failed_bookings)) * 100
    
    stats_text = (
        f"📊 <b>Подробная статистика</b>\n\n"
        
        f"👤 <b>Профиль:</b>\n"
        f"• Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n"
        f"• Статус: {'💎 Premium' if user.is_premium else f'🎁 Пробный ({user.trial_bookings}/2)'}\n"
        f"• Последняя активность: {user.last_activity.strftime('%d.%m.%Y %H:%M') if user.last_activity else 'Нет данных'}\n\n"
        
        f"🔑 <b>API ключи:</b>\n"
        f"• Всего ключей: {api_stats['total_keys']}/5\n"
        f"• Действительных: {api_stats['valid_keys']}\n"
        f"• Всего запросов: {api_stats['total_requests']}\n"
        f"• Успешность: {api_stats['success_rate']:.1%}\n\n"
        
        f"📊 <b>Мониторинги:</b>\n"
        f"• Всего создано: {total_tasks}\n"
        f"• Активных: {active_tasks}\n"
        f"• Приостановлено: {paused_tasks}\n"
        f"• Всего проверок: {total_checks}\n"
        f"• Найдено слотов: {total_slots_found}\n\n"
        
        f"🎯 <b>Бронирования:</b>\n"
        f"• Всего попыток: {total_successful_bookings + total_failed_bookings}\n"
        f"• Успешных: {total_successful_bookings}\n"
        f"• Неудачных: {total_failed_bookings}\n"
        f"• Успешность: {booking_success_rate:.1f}%\n\n"
    )
    
    if booking_stats['average_coefficient'] > 0:
        stats_text += f"📈 <b>Средний коэффициент:</b> {booking_stats['average_coefficient']:.2f}x\n\n"
    
    # Get monitoring service metrics
    monitoring_metrics = monitoring_service.get_metrics()
    if monitoring_metrics['last_check_time']:
        stats_text += (
            f"🔄 <b>Система мониторинга:</b>\n"
            f"• Последняя проверка: {monitoring_metrics['last_check_time'].strftime('%H:%M:%S')}\n"
            f"• Всего проверок: {monitoring_metrics['total_checks']}\n"
            f"• Успешных: {monitoring_metrics['successful_checks']}\n"
            f"• Ошибок: {monitoring_metrics['failed_checks']}\n"
        )
    
    from ..keyboards.inline import get_back_button
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=get_back_button("main_menu")
    )


@router.callback_query(MainMenuCallback.filter(F.action == "help"))
async def show_help_menu(callback: CallbackQuery):
    """Show help and support menu."""
    help_text = (
        "❓ <b>Помощь и поддержка</b>\n\n"
        
        "<b>🚀 Быстрый старт:</b>\n"
        "1. Добавьте API ключ Wildberries\n"
        "2. Создайте мониторинг для нужного склада\n"
        "3. Настройте фильтры и режим работы\n"
        "4. Получайте уведомления о слотах\n\n"
        
        "<b>🔧 Основные функции:</b>\n"
        "• 📊 Мониторинг - отслеживание слотов\n"
        "• 🔑 API ключи - управление доступом к WB\n"
        "• ⚙️ Настройки - конфигурация по умолчанию\n"
        "• 📈 Статистика - аналитика работы\n\n"
        
        "<b>🎯 Режимы мониторинга:</b>\n"
        "• 🔔 Уведомления - только информирование\n"
        "• 🤖 Автобронирование - автоматическая бронь\n\n"
        
        "<b>💡 Советы:</b>\n"
        "• Используйте несколько API ключей для надежности\n"
        "• Настройте коэффициенты для фильтрации дорогих слотов\n"
        "• Регулярно проверяйте валидность ключей\n"
        "• Начните с режима уведомлений для изучения\n\n"
        
        "<b>🆘 Нужна помощь?</b>\n"
        "Обратитесь в техподдержку через @support_username"
    )
    
    from ..keyboards.inline import get_back_button
    
    await callback.message.edit_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Return to main menu."""
    menu_text = (
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(
        menu_text,
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    """Handle ignore callbacks (for non-interactive buttons)."""
    await callback.answer()


# Error handler for unhandled callbacks
@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery):
    """Handle unknown callback queries."""
    await callback.answer("❓ Неизвестная команда", show_alert=True)
