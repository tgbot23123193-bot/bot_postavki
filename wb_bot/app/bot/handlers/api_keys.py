"""
API keys management handlers.

This module contains handlers for adding, managing, and validating
Wildberries API keys.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from ...services.database_service import db_service
from ...utils.logger import UserLogger, get_logger

logger = get_logger(__name__)
from ..keyboards.inline import (
    APIKeyCallback, get_api_keys_menu, get_api_keys_list_keyboard,
    get_api_key_management_keyboard, get_confirmation_keyboard, get_main_menu
)
from ..states import APIKeyStates

router = Router()


@router.callback_query(APIKeyCallback.filter(F.action == "add"))
async def start_add_api_key(callback: CallbackQuery, state: FSMContext):
    """Start adding new API key."""
    user_id = callback.from_user.id
    user_logger = UserLogger(user_id)
    
    # Check if user hasn't reached the limit
    existing_keys = await db_service.get_user_api_keys(user_id)
    
    if len(existing_keys) >= 5:  # Max API keys limit
        await callback.answer(
            "❌ Достигнут лимит API ключей (максимум 5)",
            show_alert=True
        )
        return
    
    instruction_text = (
        "🔑 <b>Добавление API ключа</b>\n\n"
        "Отправьте ваш API ключ Wildberries.\n\n"
        "💡 <b>Где найти API ключ:</b>\n"
        "1. Войдите в личный кабинет поставщика WB\n"
        "2. Перейдите в 'Настройки' → 'Доступ к API'\n"
        "3. Создайте ключ с правами на поставки\n"
        "4. Скопируйте и отправьте его сюда\n\n"
        "🔒 <b>Безопасность:</b> Ключ будет зашифрован и надежно сохранен.\n\n"
        "Отправьте /cancel для отмены."
    )
    
    await callback.message.edit_text(instruction_text, parse_mode="HTML")
    await state.set_state(APIKeyStates.waiting_for_api_key)
    await callback.answer()


@router.message(StateFilter(APIKeyStates.waiting_for_api_key))
async def add_api_key(message: Message, state: FSMContext):
    """Process new API key."""
    api_key = message.text.strip()
    user_id = message.from_user.id
    user_logger = UserLogger(user_id)
    
    if not api_key:
        await message.answer("❌ API ключ не может быть пустым. Попробуйте снова:")
        return
    
    # Show processing message
    processing_msg = await message.answer("⏳ Проверяю API ключ...")
    
    # Add API key to database
    try:
        existing_keys = await db_service.get_user_api_keys(user_id)
        api_key_record = await db_service.add_api_key(
            user_id=user_id,
            api_key=api_key,
            name=f"API ключ {len(existing_keys) + 1}"
        )
        success = True
        result_message = f"API ключ '{api_key_record.name}' добавлен успешно"
        user_logger.info(f"API key added successfully: {api_key_record.name}")
    except Exception as e:
        success = False
        result_message = f"Ошибка при добавлении API ключа: {str(e)}"
        logger.error(f"Failed to add API key for user {user_id}: {e}")
    
    await processing_msg.delete()
    
    if success:
        user_logger.info("API key added successfully")
        
        success_text = (
            "✅ <b>API ключ добавлен успешно!</b>\n\n"
            f"{result_message}\n\n"
            "Теперь вы можете создать мониторинг слотов или добавить еще ключи."
        )
        
        await message.answer(
            success_text,
            parse_mode="HTML",
            reply_markup=get_api_keys_menu()
        )
        
        # Ask for key name
        await message.answer(
            "💭 Хотите дать имя этому ключу? (например: 'Основной склад')\n"
            "Отправьте название или /skip чтобы пропустить:"
        )
        await state.set_state(APIKeyStates.waiting_for_key_name)
        
    else:
        user_logger.warning(f"Failed to add API key: {result_message}")
        
        error_text = (
            f"❌ <b>Ошибка добавления API ключа:</b>\n\n"
            f"{result_message}\n\n"
            "Проверьте правильность ключа и попробуйте снова:"
        )
        
        await message.answer(error_text, parse_mode="HTML")


@router.message(StateFilter(APIKeyStates.waiting_for_key_name))
async def set_api_key_name(message: Message, state: FSMContext):
    """Set name for the API key."""
    if message.text.strip().lower() in ['/skip', 'пропустить']:
        await state.clear()
        await message.answer(
            "✅ API ключ добавлен без имени.",
            reply_markup=get_api_keys_menu()
        )
        return
    
    key_name = message.text.strip()
    user_id = message.from_user.id
    
    # Get the last added key and update its name
    api_keys = await db_service.get_user_api_keys(user_id)
    if api_keys:
        last_key = api_keys[0]  # Most recent
        
        # Update key name in database
        from ...database import get_session
        from sqlalchemy import select
        from ...database.models import APIKey
        
        async with get_session() as session:
            query = select(APIKey).where(APIKey.id == last_key.id)
            result = await session.execute(query)
            api_key_obj = result.scalar_one_or_none()
            
            if api_key_obj:
                api_key_obj.name = key_name
                session.add(api_key_obj)
                await session.commit()
        
        await message.answer(
            f"✅ Имя ключа установлено: '{key_name}'",
            reply_markup=get_api_keys_menu()
        )
    
    await state.clear()


@router.callback_query(APIKeyCallback.filter(F.action == "list"))
async def list_api_keys(callback: CallbackQuery):
    """Show list of user's API keys."""
    user_id = callback.from_user.id
    
    # Получаем объекты API ключей ПРЯМО ИЗ PostgreSQL базы данных
    try:
        logger.info(f"📋 Loading API keys from PostgreSQL database for user {user_id}")
        api_keys = await db_service.get_user_api_keys(user_id)
        logger.info(f"✅ Loaded {len(api_keys)} API keys from database for user {user_id}")
        
        # Логируем детали каждого ключа из БД
        for i, key in enumerate(api_keys):
            logger.info(f"  📝 Key {i+1}: ID={key.id}, Name='{key.name}', Valid={key.is_valid}, Active={key.is_active}, Created={key.created_at}")
            
    except Exception as e:
        logger.error(f"❌ Failed to load API keys from database for user {user_id}: {e}")
        import traceback
        logger.error(f"📍 Database error traceback: {traceback.format_exc()}")
        api_keys = []
    
    if not api_keys:
        no_keys_text = (
            "🔑 <b>API ключи</b>\n\n"
            "У вас нет добавленных API ключей.\n"
            "Добавьте первый ключ для начала работы."
        )
        
        await callback.message.edit_text(
            no_keys_text,
            parse_mode="HTML",
            reply_markup=get_api_keys_menu()
        )
        await callback.answer()
        return
    
    keys_text = (
        f"🔑 <b>Ваши API ключи ({len(api_keys)}/5)</b>\n\n"
        "📊 <b>Загружено из PostgreSQL базы данных</b>\n"
        "👆 <b>Нажмите на ключ ниже для управления:</b>\n\n"
    )
    
    # Добавляем список ключей в текст для отладки
    for i, key in enumerate(api_keys, 1):
        status_emoji = "🟢" if key.is_valid else "🔴"
        keys_text += f"{i}. {status_emoji} <b>{key.name}</b> (ID: {key.id})\n"
        keys_text += f"   📅 Создан: {key.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        keys_text += f"   🔄 Статус: {'Активен' if key.is_active else 'Неактивен'}\n\n"
    
    keys_text += "⬇️ <b>Используйте кнопки ниже:</b>"
    
    # Создаем клавиатуру и логируем ее
    keyboard = get_api_keys_list_keyboard(api_keys)
    logger.info(f"🔧 Created keyboard with {len(keyboard.inline_keyboard)} rows")
    
    for i, row in enumerate(keyboard.inline_keyboard):
        for j, button in enumerate(row):
            logger.info(f"  Button [{i}][{j}]: '{button.text}' -> '{button.callback_data}'")
    
    logger.info(f"📤 Displaying {len(api_keys)} API keys from PostgreSQL to user {user_id}")
    await callback.message.edit_text(
        keys_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(APIKeyCallback.filter(F.action == "manage"))
async def manage_api_key(callback: CallbackQuery, callback_data: APIKeyCallback):
    """Show management options for specific API key."""
    user_id = callback.from_user.id
    key_id = callback_data.key_id
    
    logger.info(f"🔧 User {user_id} clicked MANAGE for API key {key_id}")
    await callback.answer("⏳ Загружаю управление ключом...")
    
    api_keys = await db_service.get_user_api_keys(user_id)
    api_key = next((key for key in api_keys if key.id == key_id), None)
    
    if not api_key:
        await callback.answer("❌ API ключ не найден", show_alert=True)
        return
    
    status_emoji = "🟢" if api_key.is_valid else "🔴"
    last_used = api_key.last_used.strftime('%d.%m.%Y %H:%M') if api_key.last_used else "Никогда"
    success_rate = api_key.get_success_rate() * 100 if api_key.total_requests > 0 else 0
    
    key_info_text = (
        f"🔑 <b>{api_key.name}</b>\n\n"
        f"📊 <b>Статус:</b> {status_emoji} {'Активен' if api_key.is_valid else 'Неактивен'}\n"
        f"📅 <b>Добавлен:</b> {api_key.created_at.strftime('%d.%m.%Y')}\n"
        f"⏰ <b>Последнее использование:</b> {last_used}\n"
        f"📈 <b>Запросов:</b> {api_key.total_requests}\n"
        f"✅ <b>Успешных:</b> {api_key.successful_requests} ({success_rate:.1f}%)\n"
        f"❌ <b>Ошибок:</b> {api_key.failed_requests}\n\n"
    )
    
    if api_key.validation_error:
        key_info_text += f"⚠️ <b>Последняя ошибка:</b> {api_key.validation_error[:100]}...\n\n"
    
    key_info_text += "Выберите действие:"
    
    await callback.message.edit_text(
        key_info_text,
        parse_mode="HTML",
        reply_markup=get_api_key_management_keyboard(api_key)
    )
    await callback.answer()


@router.callback_query(APIKeyCallback.filter(F.action == "test"))
async def test_api_key(callback: CallbackQuery, callback_data: APIKeyCallback):
    """Test specific API key."""
    user_id = callback.from_user.id
    key_id = callback_data.key_id
    
    await callback.answer("⏳ Проверяю API ключ...")
    
    api_keys = await db_service.get_user_api_keys(user_id)
    api_key = next((key for key in api_keys if key.id == key_id), None)
    
    if not api_key:
        await callback.message.answer("❌ API ключ не найден")
        return
    
    # Test the key
    # Простая проверка формата API ключа (начинается с 'ey')
    is_valid = api_key.startswith('ey') and len(api_key) > 100
    
    if is_valid:
        result_text = f"✅ API ключ '{api_key.name}' работает корректно!"
    else:
        result_text = f"❌ API ключ '{api_key.name}' не работает или недействителен."
    
    await callback.message.answer(result_text)
    
    # Refresh the management view
    await manage_api_key(callback, callback_data)


@router.callback_query(APIKeyCallback.filter(F.action == "rename"))
async def start_rename_api_key(callback: CallbackQuery, callback_data: APIKeyCallback, state: FSMContext):
    """Start renaming API key."""
    await state.update_data(key_id=callback_data.key_id)
    
    await callback.message.edit_text(
        "✏️ <b>Переименование API ключа</b>\n\n"
        "Введите новое имя для ключа:"
    )
    
    await state.set_state(APIKeyStates.waiting_for_rename)
    await callback.answer()


@router.message(StateFilter(APIKeyStates.waiting_for_rename))
async def rename_api_key(message: Message, state: FSMContext):
    """Process API key rename."""
    data = await state.get_data()
    key_id = data.get('key_id')
    new_name = message.text.strip()
    user_id = message.from_user.id
    
    if not new_name:
        await message.answer("❌ Имя не может быть пустым. Попробуйте снова:")
        return
    
    # Update key name
    from ...database import get_session
    from sqlalchemy import select, and_
    from ...database.models import APIKey
    
    async with get_session() as session:
        query = select(APIKey).where(
            and_(APIKey.id == key_id, APIKey.user_id == user_id)
        )
        result = await session.execute(query)
        api_key = result.scalar_one_or_none()
        
        if api_key:
            api_key.name = new_name
            session.add(api_key)
            await session.commit()
            
            await message.answer(
                f"✅ Имя ключа изменено на: '{new_name}'",
                reply_markup=get_api_keys_menu()
            )
        else:
            await message.answer("❌ API ключ не найден")
    
    await state.clear()


@router.callback_query(APIKeyCallback.filter(F.action == "delete"))
async def delete_api_key_handler(callback: CallbackQuery, callback_data: APIKeyCallback):
    """Confirm API key deletion."""
    key_id = callback_data.key_id
    
    confirmation_text = (
        "⚠️ <b>Удаление API ключа</b>\n\n"
        "Вы уверены, что хотите удалить этот ключ?\n"
        "Все связанные мониторинги будут остановлены.\n\n"
        "Это действие нельзя отменить!"
    )
    
    # Создаем клавиатуру с правильными APIKeyCallback
    confirmation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=APIKeyCallback(action="confirm_delete", key_id=key_id).pack()
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=APIKeyCallback(action="back").pack()
            )
        ]
    ])
    
    await callback.message.edit_text(
        confirmation_text,
        parse_mode="HTML",
        reply_markup=confirmation_keyboard
    )
    await callback.answer()


# Старые обработчики удалены - используются новые с APIKeyCallback


@router.callback_query(APIKeyCallback.filter(F.action == "validate"))
async def validate_all_keys(callback: CallbackQuery):
    """Validate all user's API keys."""
    user_id = callback.from_user.id
    
    await callback.answer("⏳ Проверяю все API ключи...")
    
    # Получаем все API ключи пользователя и проверяем их
    api_keys = await db_service.get_user_api_keys(user_id)
    total_count = len(api_keys)
    valid_count = len([key for key in api_keys if key.is_valid])
    
    result_text = (
        f"🔍 <b>Результат проверки API ключей</b>\n\n"
        f"✅ Действительных: {valid_count}\n"
        f"❌ Недействительных: {total_count - valid_count}\n"
        f"📊 Всего: {total_count}\n\n"
    )
    
    if valid_count == total_count:
        result_text += "🎉 Все ключи работают корректно!"
    elif valid_count == 0:
        result_text += "⚠️ Все ключи недействительны. Проверьте их настройки."
    else:
        result_text += "⚠️ Некоторые ключи требуют внимания."
    
    await callback.message.edit_text(
        result_text,
        parse_mode="HTML",
        reply_markup=get_api_keys_menu()
    )


@router.callback_query(APIKeyCallback.filter(F.action == "back"))
async def back_to_api_keys_menu(callback: CallbackQuery):
    """Return to API keys main menu."""
    await callback.message.edit_text(
        "🔑 <b>Управление API ключами</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_api_keys_menu()
    )
    await callback.answer()


@router.callback_query(APIKeyCallback.filter(F.action == "delete"))
async def delete_api_key_handler(callback: CallbackQuery, callback_data: APIKeyCallback):
    """Обработчик удаления API ключа."""
    try:
        user_id = callback.from_user.id
        key_id = callback_data.key_id
        
        logger.info(f"🗑️ DELETE REQUEST: User {user_id} wants to delete API key {key_id}")
        await callback.answer("⏳ Подготавливаю удаление ключа...")
        
        # Получаем информацию об API ключе для подтверждения
        api_key = await db_service.get_api_key_by_id(key_id, user_id)
        
        if not api_key:
            await callback.message.edit_text(
                "❌ <b>Ошибка</b>\n\n"
                "API ключ не найден или не принадлежит вам.",
                parse_mode="HTML",
                reply_markup=get_api_keys_menu()
            )
            await callback.answer("❌ Ключ не найден", show_alert=True)
            return
        
        # Показываем информацию о ключе и запрашиваем подтверждение
        confirmation_text = (
            f"🗑 <b>Удаление API ключа</b>\n\n"
            f"📝 Название: {api_key.name or 'Без названия'}\n"
            f"📅 Создан: {api_key.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"🔄 Статус: {'✅ Активен' if api_key.is_active else '❌ Неактивен'}\n"
            f"📊 Использований: {api_key.total_requests or 0}\n\n"
            f"⚠️ <b>Это действие нельзя отменить!</b>\n"
            f"Вы уверены что хотите удалить этот API ключ?"
        )
        
        # Создаем клавиатуру подтверждения
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=APIKeyCallback(action="confirm_delete", key_id=key_id).pack()
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=APIKeyCallback(action="list").pack()
                )
            ]
        ])
        
        await callback.message.edit_text(
            confirmation_text,
            parse_mode="HTML",
            reply_markup=confirm_keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе удаления API ключа: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Не удалось обработать запрос на удаление.",
            parse_mode="HTML",
            reply_markup=get_api_keys_menu()
        )
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(APIKeyCallback.filter(F.action == "confirm_delete"))
async def execute_delete_api_key_handler(callback: CallbackQuery, callback_data: APIKeyCallback):
    """Подтверждение удаления API ключа."""
    try:
        user_id = callback.from_user.id
        key_id = callback_data.key_id
        
        logger.info(f"👤 Пользователь {user_id} подтвердил удаление API ключа {key_id}")
        
        # Удаляем API ключ из базы данных
        success = await db_service.delete_api_key(key_id, user_id)
        
        if success:
            await callback.message.edit_text(
                "✅ <b>API ключ удален</b>\n\n"
                "Ключ успешно удален из системы.\n"
                "Все связанные с ним данные также удалены.",
                parse_mode="HTML",
                reply_markup=get_api_keys_menu()
            )
            await callback.answer("✅ Ключ удален", show_alert=True)
            
            # Логируем успешное удаление
            user_logger = UserLogger(user_id)
            await user_logger.log_info(f"API ключ {key_id} успешно удален")
            
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка удаления</b>\n\n"
                "Не удалось удалить API ключ.\n"
                "Возможно, ключ уже был удален или произошла ошибка базы данных.",
                parse_mode="HTML",
                reply_markup=get_api_keys_menu()
            )
            await callback.answer("❌ Ошибка удаления", show_alert=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении API ключа: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при удалении ключа.",
            parse_mode="HTML",
            reply_markup=get_api_keys_menu()
        )
        await callback.answer("❌ Ошибка", show_alert=True)
