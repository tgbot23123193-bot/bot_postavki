"""
Base command handlers for the bot.

This module contains handlers for basic commands like /start, /help,
and main menu navigation.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from ..keyboards.inline import get_main_menu, MainMenuCallback
from ...services.database_service import db_service
from ...utils.logger import get_logger

logger = get_logger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    user_id = message.from_user.id
    logger.info(f"🚀 START command from user {user_id}")
    
    # Создаем или обновляем пользователя в базе данных
    try:
        logger.info(f"📝 Creating/updating user {user_id}")
        await db_service.get_or_create_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        logger.info(f"✅ User {user_id} created/updated")
        
        # Получаем API ключи пользователя из базы данных
        logger.info(f"🔍 Getting API keys for user {user_id}")
        api_keys = await db_service.get_user_api_keys(user_id)
        has_api_keys_db = len(api_keys) > 0
        logger.info(f"🔑 Found {len(api_keys)} API keys for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to create/update user {user_id}: {e}")
        import traceback
        logger.error(f"📍 Traceback: {traceback.format_exc()}")
        has_api_keys_db = False  # В случае ошибки считаем что ключей нет
    
    # Проверяем есть ли у пользователя API ключи
    logger.info(f"🔍 Checking has_api_keys_db for user {user_id}: {has_api_keys_db}")
    if has_api_keys_db:
        # У пользователя есть API ключи - показываем главное меню
        logger.info(f"✅ Showing MAIN MENU to user {user_id} (has API keys)")
        greeting = f"Привет, {message.from_user.first_name}! 👋"
        menu_text = (
            f"{greeting}\n\n"
            "🤖 <b>WB Auto-Booking Bot</b> готов к работе!\n\n"
            "✅ API ключи настроены\n"
            "Выберите действие из меню ниже:"
        )
        
        await message.answer(
            menu_text,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        logger.info(f"📤 MAIN MENU sent to user {user_id}")
    else:
        # У пользователя нет API ключей - запрашиваем добавление
        logger.info(f"❌ Showing ADD API KEY menu to user {user_id} (no API keys)")
        welcome_text = (
            "🎉 <b>Добро пожаловать в WB Auto-Booking Bot!</b>\n\n"
            "Этот бот поможет вам:\n"
            "📊 Мониторить доступные слоты поставок\n"
            "🤖 Автоматически бронировать подходящие слоты\n"
            "📱 Получать уведомления о найденных слотах\n"
            "📈 Отслеживать статистику ваших поставок\n\n"
            "🎁 <b>Пробный период:</b> 2 бесплатные поймаСТВки\n"
            "После этого потребуется оформление подписки.\n\n"
            "Для начала работы добавьте ваш API ключ Wildberries:"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Добавить API ключ", callback_data="add_api_key")],
            [InlineKeyboardButton(text="❓ Как получить API ключ?", callback_data="help_api_key")]
        ])
        
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = (
        "📖 <b>Справка по боту</b>\n\n"
        
        "<b>🎯 Основные функции:</b>\n"
        "• Мониторинг слотов поставок Wildberries\n"
        "• Автоматическое бронирование при появлении слотов\n"
        "• Настройка фильтров по коэффициентам приемки\n"
        "• Выбор типа поставки (короб/монопаллета)\n"
        "• Выбор типа доставки (прямая/транзитная)\n\n"
        
        "<b>🔧 Настройки мониторинга:</b>\n"
        "• <b>Интервал проверки:</b> от 30 секунд до 10 минут\n"
        "• <b>Коэффициенты:</b> x1, x2, x3, x5 (фильтр дорогих слотов)\n"
        "• <b>Режимы:</b> только уведомления или автобронирование\n\n"
        
        "<b>🔑 API ключи:</b>\n"
        "• Максимум 5 ключей на пользователя\n"
        "• Автоматическая проверка валидности\n"
        "• Безопасное шифрование в базе данных\n\n"
        
        "<b>💎 Пробный период:</b>\n"
        "• 2 бесплатные поймаССки для новых пользователей\n"
        "• Полный функционал во время пробного периода\n\n"
        
        "<b>📱 Команды:</b>\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/stats - Статистика\n"
        "/cancel - Отмена текущего действия\n\n"
        
        "<b>🆘 Поддержка:</b>\n"
        "Если возникли вопросы, используйте кнопку '❓ Помощь' в главном меню."
    )
    
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_menu())


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats command."""
    user_id = message.from_user.id
    
    try:
        # Получаем статистику пользователя из базы данных
        stats = await db_service.get_user_stats(user_id)
        
        if stats and stats.get('user'):
            user = stats['user']
            keys_count = stats.get('api_keys_count', 0)
            active_tasks = stats.get('active_tasks_count', 0)
            total_bookings = stats.get('total_bookings', 0)
            successful_bookings = stats.get('successful_bookings', 0)
            trial_left = stats.get('trial_bookings_left')
            
            # Calculate stats
            stats_text = (
                f"📊 <b>Ваша статистика</b>\n\n"
                f"👤 <b>Пользователь:</b> {message.from_user.first_name}\n"
                f"🔑 <b>API ключей:</b> {keys_count}/5\n"
                f"💎 <b>Статус:</b> {'✅ Готов к работе' if keys_count > 0 else '❌ Нужен API ключ'}\n"
                f"🎁 <b>Пробные бронирования:</b> {trial_left if trial_left is not None else 'Премиум'}\n\n"
                
                f"📈 <b>Активность:</b>\n"
                f"📊 Активных мониторингов: {active_tasks}\n"
                f"🎯 Всего бронирований: {total_bookings}\n"
                f"✅ Успешных бронирований: {successful_bookings}\n"
                f"📈 Процент успеха: {(successful_bookings/total_bookings*100) if total_bookings > 0 else 0:.1f}%\n\n"
                
                "Для подробной статистики используйте кнопку '📈 Статистика' в главном меню."
            )
        else:
            # Fallback если пользователь не найден
            stats_text = (
                f"📊 <b>Ваша статистика</b>\n\n"
                f"👤 <b>Пользователь:</b> {message.from_user.first_name}\n"
                f"❌ Данные не найдены. Используйте /start для регистрации."
            )
            
    except Exception as e:
        logger.error(f"Failed to get user stats {user_id}: {e}")
        # Fallback to in-memory storage
        from .callbacks import get_user_keys_count, has_api_keys
        
        keys_count = await get_user_keys_count(user_id)
        has_keys = await has_api_keys(user_id)
        stats_text = (
            f"📊 <b>Ваша статистика</b>\n\n"
            f"👤 <b>Пользователь:</b> {message.from_user.first_name}\n"
            f"🔑 <b>API ключей:</b> {keys_count}/5\n"
            f"💎 <b>Статус:</b> {'✅ Готов к работе' if has_keys else '❌ Нужен API ключ'}\n\n"
            
            f"📈 <b>Активность:</b>\n"
            f"📊 Активных мониторингов: 0\n"
            f"🎯 Успешных бронирований: 0\n\n"
            
            "Для подробной статистики используйте кнопку '📈 Статистика' в главном меню."
        )
    
    await message.answer(stats_text, parse_mode="HTML", reply_markup=get_main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Handle /cancel command."""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "❌ Нет активных действий для отмены.",
            reply_markup=get_main_menu()
        )
        return
    
    await state.clear()
    await message.answer(
        "✅ Текущее действие отменено.",
        reply_markup=get_main_menu()
    )


# Main menu callback handler
@router.callback_query(MainMenuCallback.filter())
async def handle_main_menu(callback: CallbackQuery, callback_data: MainMenuCallback):
    """Handle main menu callbacks."""
    action = callback_data.action
    
    if action == "main":
        menu_text = (
            "🏠 <b>Главное меню</b>\n\n"
            "Выберите действие:"
        )
        await callback.message.edit_text(
            menu_text,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    
    elif action == "help":
        # Redirect to help handler
        await cmd_help(callback.message)
    
    elif action == "stats":
        # This will be handled by dedicated stats handler
        await callback.answer("📊 Загрузка статистики...")
    
    else:
        # Other actions are handled by dedicated routers
        await callback.answer()




# УДАЛЕН: обработчик handle_unknown_message 
# который перехватывал все сообщения и мешал FSM
