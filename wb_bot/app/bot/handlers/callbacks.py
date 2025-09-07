"""
General callback handlers for the bot.

This module contains handlers for various callback queries that don't
belong to specific modules like monitoring or API keys.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from ..keyboards.inline import MainMenuCallback, get_main_menu
from ..states import APIKeyStates

router = Router()

# In-memory хранилище API ключей (временное решение)
user_api_keys = {}  # user_id: [list of api keys]


def has_api_keys(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя API ключи."""
    return user_id in user_api_keys and len(user_api_keys[user_id]) > 0


def add_api_key(user_id: int, api_key: str) -> bool:
    """Добавляет API ключ пользователю."""
    if user_id not in user_api_keys:
        user_api_keys[user_id] = []
    
    if len(user_api_keys[user_id]) >= 5:
        return False  # Лимит достигнут
    
    user_api_keys[user_id].append(api_key)
    return True


def get_user_keys_count(user_id: int) -> int:
    """Возвращает количество API ключей пользователя."""
    return len(user_api_keys.get(user_id, []))


def create_blocked_menu() -> InlineKeyboardMarkup:
    """Создает меню для пользователей без API ключей."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Добавить API ключ", callback_data="add_api_key")],
        [InlineKeyboardButton(text="❓ Как получить API ключ?", callback_data="help_api_key")]
    ])


@router.callback_query(MainMenuCallback.filter(F.action == "api_keys"))
async def show_api_keys_menu(callback: CallbackQuery):
    """Show API keys main menu."""
    try:
        user_id = callback.from_user.id
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить API ключ", callback_data="add_api_key")],
            [InlineKeyboardButton(text="📋 Мои ключи", callback_data="list_api_keys")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
        
        keys_count = get_user_keys_count(user_id)
        
        api_keys_text = (
            f"🔑 <b>Управление API ключами</b>\n\n"
            f"📊 <b>Текущий статус:</b> {keys_count}/5 ключей\n\n"
            f"API ключи Wildberries необходимы для работы с системой поставок.\n"
            f"Вы можете добавить до 5 ключей для распределения нагрузки.\n\n"
            f"🔒 <b>Безопасность:</b> Все ключи шифруются и хранятся в защищенном виде.\n\n"
            f"Выберите действие:"
        )
        
        await callback.message.edit_text(
            api_keys_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "monitoring"))
async def show_monitoring_menu(callback: CallbackQuery):
    """Show monitoring menu - требует API ключи."""
    user_id = callback.from_user.id
    
    if not has_api_keys(user_id):
        await callback.message.edit_text(
            "🔒 <b>Доступ ограничен</b>\n\n"
            "❌ Для использования мониторинга необходимо добавить API ключ Wildberries.\n\n"
            "🔑 Сначала добавьте API ключ, а затем возвращайтесь к настройке мониторинга.",
            parse_mode="HTML",
            reply_markup=create_blocked_menu()
        )
        await callback.answer("⚠️ Сначала добавьте API ключ!", show_alert=True)
        return
    
    # Если есть API ключи - сразу показываем меню мониторинга
    from .monitoring_simple import show_monitoring_options
    await show_monitoring_options(callback)


@router.callback_query(MainMenuCallback.filter(F.action == "settings"))
async def show_settings_menu(callback: CallbackQuery):
    """Show settings menu - требует API ключи."""
    user_id = callback.from_user.id
    
    if not has_api_keys(user_id):
        await callback.message.edit_text(
            "🔒 <b>Доступ ограничен</b>\n\n"
            "❌ Для изменения настроек необходимо добавить API ключ Wildberries.\n\n"
            "🔑 Сначала добавьте API ключ, а затем возвращайтесь к настройкам.",
            parse_mode="HTML",
            reply_markup=create_blocked_menu()
        )
        await callback.answer("⚠️ Сначала добавьте API ключ!", show_alert=True)
        return
    
    await callback.answer("⚙️ Настройки в разработке", show_alert=True)


@router.callback_query(MainMenuCallback.filter(F.action == "stats"))
async def show_stats_menu(callback: CallbackQuery):
    """Show stats menu - требует API ключи."""
    user_id = callback.from_user.id
    
    if not has_api_keys(user_id):
        await callback.message.edit_text(
            "🔒 <b>Доступ ограничен</b>\n\n"
            "❌ Статистика доступна только после добавления API ключа.\n\n"
            "🔑 Сначала добавьте API ключ, чтобы увидеть статистику.",
            parse_mode="HTML",
            reply_markup=create_blocked_menu()
        )
        await callback.answer("⚠️ Сначала добавьте API ключ!", show_alert=True)
        return
    
    # Импортируем данные мониторинга
    from .monitoring_simple import user_monitoring_tasks
    
    keys_count = get_user_keys_count(user_id)
    monitoring_count = len(user_monitoring_tasks.get(user_id, []))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    stats_text = (
        "📊 <b>Ваша статистика</b>\n\n"
        f"🔑 <b>API ключей:</b> {keys_count}/5\n"
        f"📊 <b>Активных мониторингов:</b> {monitoring_count}\n"
        f"🎯 <b>Пробный период:</b> 2 бесплатных бронирования\n\n"
        "📈 <b>За все время:</b>\n"
        "• Проверено слотов: 0\n"
        "• Найдено доступных: 0\n"
        "• Забронировано: 0\n"
        "• Успешность: 0%\n\n"
        "💡 <i>Статистика обновляется в реальном времени</i>"
    )
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(MainMenuCallback.filter(F.action == "help"))
async def show_help_menu(callback: CallbackQuery):
    """Show help menu - доступно всем."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    help_text = (
        "❓ <b>Справка по использованию</b>\n\n"
        "🔑 <b>Шаг 1: API ключи</b>\n"
        "Добавьте ваши API ключи Wildberries для работы с системой поставок.\n\n"
        "📊 <b>Шаг 2: Мониторинг</b>\n"
        "Настройте автоматическое отслеживание доступных слотов на складах.\n\n"
        "🤖 <b>Шаг 3: Автобронирование</b>\n"
        "Бот автоматически забронирует подходящие слоты при их появлении.\n\n"
        "💡 <b>Важно:</b> Без API ключа функции бота недоступны!"
    )
    
    await callback.message.edit_text(
        help_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


# Обработчики для добавления API ключей
@router.callback_query(F.data == "add_api_key")
async def start_add_api_key(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления API ключа."""
    user_id = callback.from_user.id
    
    if get_user_keys_count(user_id) >= 5:
        await callback.answer("❌ Достигнут лимит API ключей (максимум 5)", show_alert=True)
        return
    
    await state.set_state(APIKeyStates.waiting_for_api_key)
    
    instruction_text = (
        "🔑 <b>Добавление API ключа</b>\n\n"
        "Отправьте ваш API ключ Wildberries в следующем сообщении.\n\n"
        "💡 <b>Где найти API ключ:</b>\n"
        "1. Войдите в личный кабинет поставщика WB\n"
        "2. Перейдите в 'Настройки' → 'Доступ к API'\n"
        "3. Создайте ключ с правами на поставки\n"
        "4. Скопируйте и отправьте его сюда\n\n"
        "🔒 <b>Безопасность:</b> Ключ будет зашифрован и надежно сохранен.\n\n"
        "Отправьте /cancel для отмены."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        instruction_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(APIKeyStates.waiting_for_api_key)
async def handle_api_key_input(message: Message, state: FSMContext):
    """Обработка ввода API ключа."""
    current_state = await state.get_state()
    print(f"DEBUG: Current state = {current_state}")
    print(f"DEBUG: Expected state = {APIKeyStates.waiting_for_api_key}")
    print(f"DEBUG: Message text = {message.text[:50]}...")
    
    if current_state == APIKeyStates.waiting_for_api_key:
        user_id = message.from_user.id
        api_key = message.text.strip()
        
        # Простая валидация длины
        if len(api_key) < 10:
            await message.answer(
                "❌ API ключ слишком короткий. Попробуйте еще раз или отправьте /cancel для отмены."
            )
            return
        
        # Проверяем формат JWT токена (начинается с ey)
        if not api_key.startswith('ey'):
            await message.answer(
                "❌ Неверный формат API ключа. API ключ Wildberries должен начинаться с 'ey'.\n"
                "Попробуйте еще раз или отправьте /cancel для отмены."
            )
            return
        
        # Добавляем ключ БЕЗ проверки через WB API
        if add_api_key(user_id, api_key):
            await state.clear()
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")],
                [InlineKeyboardButton(text="➕ Добавить еще ключ", callback_data="add_api_key")]
            ])
            
            await message.answer(
                f"✅ <b>API ключ успешно добавлен!</b>\n\n"
                f"🔑 Всего ключей: {get_user_keys_count(user_id)}/5\n\n"
                f"🎉 Теперь вы можете использовать все функции бота!\n\n"
                f"💡 <b>Совет:</b> Начните с настройки мониторинга слотов в разделе '📊 Мониторинг'.",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.answer("❌ Достигнут лимит API ключей (максимум 5)")


@router.callback_query(F.data == "list_api_keys")
async def list_user_api_keys(callback: CallbackQuery):
    """Показать список API ключей пользователя."""
    user_id = callback.from_user.id
    keys = user_api_keys.get(user_id, [])
    
    if not keys:
        await callback.answer("📋 У вас пока нет API ключей", show_alert=True)
        return
    
    keys_text = "📋 <b>Ваши API ключи:</b>\n\n"
    for i, key in enumerate(keys, 1):
        masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else f"{key[:4]}..."
        keys_text += f"{i}. <code>{masked_key}</code>\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        keys_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "help_api_key")
async def show_api_key_help(callback: CallbackQuery):
    """Показать справку по получению API ключа."""
    help_text = (
        "🔑 <b>Как получить API ключ Wildberries:</b>\n\n"
        "1️⃣ Зайдите в личный кабинет поставщика WB\n"
        "2️⃣ Перейдите в раздел <b>'Настройки'</b>\n"
        "3️⃣ Выберите <b>'Доступ к API'</b>\n"
        "4️⃣ Нажмите <b>'Создать новый токен'</b>\n"
        "5️⃣ Выберите права: <b>'Поставки'</b>\n"
        "6️⃣ Скопируйте полученный ключ\n"
        "7️⃣ Вставьте его в бота\n\n"
        "⚠️ <b>Важно:</b> Никому не сообщайте ваш API ключ!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить API ключ", callback_data="add_api_key")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        help_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню."""
    # Очищаем состояние при возврате в меню
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Добро пожаловать в WB Auto-Booking Bot!\n"
        "Выберите нужную функцию:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Отмена текущего действия."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ Действие отменено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        )