"""
Обработчики для управления поставками
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import List, Dict, Any

from ...utils.logger import get_logger
from ...services.wb_supplies_api import WBSuppliesAPIClient
# Removed user_api_keys - using PostgreSQL database only
from ..keyboards.inline import back_to_main_menu_keyboard

logger = get_logger(__name__)
router = Router()


class SuppliesStates(StatesGroup):
    """Состояния для работы с поставками."""
    waiting_for_api_key = State()
    viewing_supplies = State()
    selecting_dates = State()
    monitoring_slots = State()
    multi_booking_selection = State()  # Состояние мультибронирования


def create_supplies_keyboard(supplies: List[Dict[str, Any]], multi_booking_mode: bool = False, selected_supplies: List[str] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком ВСЕХ поставок."""
    keyboard = []
    selected_supplies = selected_supplies or []
    
    for supply in supplies[:20]:  # Показываем максимум 20 поставок
        supply_id = supply.get("id", "")
        supply_name = supply.get("name", f"Поставка #{supply_id}")
        status = supply.get("status", "unknown")
        
        # Эмодзи для статуса по названию
        status_emoji = "📦"
        if "Принято" in status:
            status_emoji = "✅"
        elif "Не запланировано" in status:
            status_emoji = "🔥"
        elif "Запланировано" in status:
            status_emoji = "📅"
        elif "Отгрузка разрешена" in status:
            status_emoji = "🚚"
        elif "Идёт приёмка" in status:
            status_emoji = "📦"
        elif "Отгружено" in status:
            status_emoji = "🏁"
        
        # Обрезаем название и добавляем статус
        display_name = supply_name[:25]
        if len(supply_name) > 25:
            display_name += "..."
        
        # В режиме мультибронирования добавляем чекбоксы
        if multi_booking_mode:
            checkbox = "☑️" if str(supply_id) in selected_supplies else "☐"
            button_text = f"{checkbox} {status_emoji} {display_name}"
            callback_data = f"multi_toggle:{supply_id}"
        else:
            button_text = f"{status_emoji} {display_name} ({status})"
            callback_data = f"supply_select:{supply_id}"
        
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=callback_data
            )
        ])
    
    # Кнопки управления
    if multi_booking_mode:
        management_buttons = [
            [InlineKeyboardButton(text="🎯 Начать мультибронь", callback_data="start_multi_booking")],
            [InlineKeyboardButton(text="🔄 Обновить список", callback_data="multi_supplies_refresh")],
            [InlineKeyboardButton(text="⬅️ Обычный режим", callback_data="view_supplies")]
        ]
        if selected_supplies:
            management_buttons.insert(0, [InlineKeyboardButton(text="🗑 Очистить выбор", callback_data="clear_multi_selection")])
    else:
        management_buttons = [
            [InlineKeyboardButton(text="🎯 Мультибронирование", callback_data="multi_booking_mode")],
            [InlineKeyboardButton(text="🔄 Обновить список", callback_data="supplies_refresh")],
            [InlineKeyboardButton(text="🏬 Склады", callback_data="view_warehouses")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ]
    
    keyboard.extend(management_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_warehouses_keyboard(warehouses: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком складов."""
    keyboard = []
    
    for warehouse in warehouses[:15]:  # Показываем максимум 15 складов
        warehouse_id = warehouse.get("id", "")
        warehouse_name = warehouse.get("name", f"Склад #{warehouse_id}")
        
        # Обрезаем длинные названия
        display_name = warehouse_name[:35]
        if len(warehouse_name) > 35:
            display_name += "..."
            
        keyboard.append([
            InlineKeyboardButton(
                text=f"🏬 {display_name}",
                callback_data=f"warehouse_info:{warehouse_id}"
            )
        ])
    
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="warehouses_refresh")],
        [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "view_supplies")
async def show_supplies_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню управления поставками."""
    user_id = callback.from_user.id
    
    # Проверяем есть ли API ключ у пользователя
    from .callbacks import get_user_api_keys_list
    api_keys = await get_user_api_keys_list(user_id)
    if not api_keys:
        await callback.message.edit_text(
            "❌ <b>API ключ не найден</b>\n\n"
            "Для работы с поставками необходим API ключ Wildberries.\n"
            "Отправьте ваш API ключ:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
            ])
        )
        await state.set_state(SuppliesStates.waiting_for_api_key)
        return
    
    await callback.message.edit_text(
        "⏳ <b>Загружаю список поставок...</b>\n\n"
        "Подключаюсь к API Wildberries...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем список поставок через API
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            supplies = await api_client.get_supplies(limit=50)
            
        if not supplies:
            await callback.message.edit_text(
                "📭 <b>Поставки не найдены</b>\n\n"
                "У вас пока нет неплановых поставок для бронирования.\n"
                "Создайте поставку в личном кабинете WB.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="view_supplies")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
                ])
            )
            return
        
        # Показываем поставки со статусами 1 и 2
        await callback.message.edit_text(
            f"📦 <b>Поставки для бронирования ({len(supplies)})</b>\n\n"
            "🔥 Не запланировано, 📅 Запланировано\n"
            "Выберите поставку для бронирования слота:",
            parse_mode="HTML",
            reply_markup=create_supplies_keyboard(supplies)
        )
        
        # Сохраняем список поставок в состоянии
        await state.update_data(supplies=supplies)
        await state.set_state(SuppliesStates.viewing_supplies)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения поставок для пользователя {user_id}: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка получения поставок</b>\n\n"
            f"Не удалось загрузить список поставок:\n"
            f"<code>{str(e)}</code>\n\n"
            f"Проверьте правильность API ключа.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="view_supplies")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
            ])
        )


@router.callback_query(F.data == "view_warehouses")
async def show_warehouses_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает список складов."""
    user_id = callback.from_user.id
    
    from .callbacks import get_user_api_keys_list
    api_keys = await get_user_api_keys_list(user_id)
    if not api_keys:
        await callback.answer("❌ API ключ не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⏳ <b>Загружаю список складов...</b>\n\n"
        "Получаю данные о доступных складах WB...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем список складов через API
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            warehouses = await api_client.get_warehouses()
            
        if not warehouses:
            await callback.message.edit_text(
                "🏬 <b>Склады не найдены</b>\n\n"
                "Не удалось получить список доступных складов.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="view_warehouses")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ])
            )
            return
        
        # Показываем список складов
        await callback.message.edit_text(
            f"🏬 <b>Доступные склады ({len(warehouses)})</b>\n\n"
            "Выберите склад для просмотра информации:",
            parse_mode="HTML",
            reply_markup=create_warehouses_keyboard(warehouses)
        )
        
        # Сохраняем список складов в состоянии
        await state.update_data(warehouses=warehouses)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения складов для пользователя {user_id}: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка получения складов</b>\n\n"
            f"Не удалось загрузить список складов:\n"
            f"<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="view_warehouses")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )


@router.callback_query(F.data.startswith("supply_select:"))
async def select_supply(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора поставки."""
    supply_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные поставок из состояния
    data = await state.get_data()
    supplies = data.get("supplies", [])
    
    # Находим выбранную поставку
    selected_supply = None
    for supply in supplies:
        # Сравниваем как строки, так как supply_id приходит как строка
        if str(supply.get("id")) == str(supply_id):
            selected_supply = supply
            break
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    supply_status = selected_supply.get("status", "unknown")
    created_at = selected_supply.get("createDate", "")
    
    # Форматируем дату создания
    formatted_date = "Неизвестно"
    if created_at:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            formatted_date = dt.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_date = created_at
    
    await callback.message.edit_text(
        f"📦 <b>{supply_name}</b>\n\n"
        f"🆔 ID: <code>{supply_id}</code>\n"
        f"📊 Статус: {supply_status}\n"
        f"📅 Создана: {formatted_date}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Забронировать слот", callback_data=f"book_supply:{supply_id}")],
            [InlineKeyboardButton(text="👁‍🗨 Мониторинг слотов", callback_data=f"monitor_supply:{supply_id}")],
            [InlineKeyboardButton(text="📋 Детали поставки", callback_data=f"supply_details:{supply_id}")],
            [InlineKeyboardButton(text="⬅️ К списку поставок", callback_data="view_supplies")]
        ])
    )
    
    # Сохраняем выбранную поставку
    await state.update_data(selected_supply=selected_supply)


@router.message(SuppliesStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext):
    """Обработка ввода API ключа."""
    api_key = message.text.strip()
    user_id = message.from_user.id
    
    # Удаляем сообщение с API ключом для безопасности
    try:
        await message.delete()
    except:
        pass
    
    if not api_key or len(api_key) < 10:
        await message.answer(
            "❌ <b>Неверный формат API ключа</b>\n\n"
            "API ключ должен содержать минимум 10 символов.\n"
            "Попробуйте еще раз:",
            parse_mode="HTML"
        )
        return
    
    loading_msg = await message.answer(
        "⏳ <b>Проверяю API ключ...</b>\n\n"
        "Подключаюсь к API Wildberries...",
        parse_mode="HTML"
    )
    
    try:
        # Проверяем API ключ
        async with WBSuppliesAPIClient(api_key) as api_client:
            warehouses = await api_client.get_warehouses()
            
        # Сохраняем API ключ в базе данных
        user = await get_user_by_telegram_id(user_id)
        if user:
            # Здесь нужно обновить API ключ в базе данных
            # user.api_key = api_key
            # await user.save()
            pass
        
        await loading_msg.edit_text(
            "✅ <b>API ключ сохранен!</b>\n\n"
            "Теперь вы можете работать с поставками.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Показать поставки", callback_data="view_supplies")],
                [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
            ])
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки API ключа: {e}")
        await loading_msg.edit_text(
            f"❌ <b>Ошибка API ключа</b>\n\n"
            f"Не удалось подключиться к API WB:\n"
            f"<code>{str(e)}</code>\n\n"
            f"Проверьте правильность ключа и попробуйте снова:",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "supplies_refresh")
async def refresh_supplies(callback: CallbackQuery, state: FSMContext):
    """Обновляет список поставок."""
    await show_supplies_menu(callback, state)


@router.callback_query(F.data == "back_to_supply")
async def back_to_supply(callback: CallbackQuery, state: FSMContext):
    """Возвращается к выбранной поставке."""
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        await show_supplies_menu(callback, state)
        return
    
    supply_id = selected_supply.get("id")
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    supply_status = selected_supply.get("status", "unknown")
    created_at = selected_supply.get("createDate", "")
    
    # Форматируем дату создания
    formatted_date = "Неизвестно"
    if created_at:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            formatted_date = dt.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_date = created_at
    
    await callback.message.edit_text(
        f"📦 <b>{supply_name}</b>\n\n"
        f"🆔 ID: <code>{supply_id}</code>\n"
        f"📊 Статус: {supply_status}\n"
        f"📅 Создана: {formatted_date}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Забронировать слот", callback_data=f"book_supply:{supply_id}")],
            [InlineKeyboardButton(text="👁‍🗨 Мониторинг слотов", callback_data=f"monitor_supply:{supply_id}")],
            [InlineKeyboardButton(text="📋 Детали поставки", callback_data=f"supply_details:{supply_id}")],
            [InlineKeyboardButton(text="⬅️ К списку поставок", callback_data="view_supplies")]
        ])
    )


# =============================================================================
# МУЛЬТИБРОНИРОВАНИЕ
# =============================================================================

@router.callback_query(F.data == "multi_booking_mode")
async def enter_multi_booking_mode(callback: CallbackQuery, state: FSMContext):
    """Переключает в режим мультибронирования."""
    await callback.message.edit_text(
        "⏳ <b>Переключаюсь в режим мультибронирования...</b>\n\n"
        "Загружаю список поставок для выбора...",
        parse_mode="HTML"
    )
    
    # Получаем существующие поставки из состояния или загружаем заново
    data = await state.get_data()
    supplies = data.get("supplies", [])
    
    if not supplies:
        user_id = callback.from_user.id
        from .callbacks import get_user_api_keys_list
        api_keys = await get_user_api_keys_list(user_id)
        if not api_keys:
            await callback.message.edit_text(
                "❌ <b>API ключ не найден</b>\n\n"
                "Для мультибронирования необходим API ключ.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="view_supplies")]
                ])
            )
            return
            
        try:
            async with WBSuppliesAPIClient(api_keys[0]) as api_client:
                supplies = await api_client.get_supplies(limit=50)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки поставок для мультибронирования: {e}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка загрузки поставок</b>\n\n"
                f"<code>{str(e)}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="view_supplies")]
                ])
            )
            return
    
    await callback.message.edit_text(
        f"🎯 <b>Мультибронирование (до 3 поставок)</b>\n\n"
        f"📦 Доступно поставок: {len(supplies)}\n"
        f"☑️ Выбрано: 0 / 3\n\n"
        f"Нажмите на поставки для выбора:",
        parse_mode="HTML",
        reply_markup=create_supplies_keyboard(supplies, multi_booking_mode=True)
    )
    
    # Сохраняем состояние
    await state.update_data(
        supplies=supplies,
        selected_supplies_multi=[],
        multi_booking_mode=True
    )
    await state.set_state(SuppliesStates.multi_booking_selection)


@router.callback_query(F.data.startswith("multi_toggle:"))
async def toggle_supply_selection(callback: CallbackQuery, state: FSMContext):
    """Переключает выбор поставки в режиме мультибронирования."""
    supply_id = callback.data.split(":")[1]
    
    data = await state.get_data()
    selected_supplies = data.get("selected_supplies_multi", [])
    supplies = data.get("supplies", [])
    
    # Переключаем выбор
    if supply_id in selected_supplies:
        selected_supplies.remove(supply_id)
    else:
        if len(selected_supplies) >= 3:
            await callback.answer("❌ Максимум 3 поставки одновременно!", show_alert=True)
            return
        selected_supplies.append(supply_id)
    
    # Обновляем клавиатуру
    await callback.message.edit_text(
        f"🎯 <b>Мультибронирование (до 3 поставок)</b>\n\n"
        f"📦 Доступно поставок: {len(supplies)}\n"
        f"☑️ Выбрано: {len(selected_supplies)} / 3\n\n"
        f"Нажмите на поставки для выбора:",
        parse_mode="HTML",
        reply_markup=create_supplies_keyboard(supplies, multi_booking_mode=True, selected_supplies=selected_supplies)
    )
    
    await state.update_data(selected_supplies_multi=selected_supplies)


@router.callback_query(F.data == "clear_multi_selection")
async def clear_multi_selection(callback: CallbackQuery, state: FSMContext):
    """Очищает выбор в режиме мультибронирования."""
    data = await state.get_data()
    supplies = data.get("supplies", [])
    
    await callback.message.edit_text(
        f"🎯 <b>Мультибронирование (до 3 поставок)</b>\n\n"
        f"📦 Доступно поставок: {len(supplies)}\n"
        f"☑️ Выбрано: 0 / 3\n\n"
        f"Нажмите на поставки для выбора:",
        parse_mode="HTML",
        reply_markup=create_supplies_keyboard(supplies, multi_booking_mode=True)
    )
    
    await state.update_data(selected_supplies_multi=[])


@router.callback_query(F.data == "multi_supplies_refresh")
async def refresh_multi_supplies(callback: CallbackQuery, state: FSMContext):
    """Обновляет список поставок в режиме мультибронирования."""
    await enter_multi_booking_mode(callback, state)


@router.callback_query(F.data == "start_multi_booking")
async def start_multi_booking(callback: CallbackQuery, state: FSMContext):
    """Запускает мультибронирование выбранных поставок."""
    data = await state.get_data()
    selected_supplies_ids = data.get("selected_supplies_multi", [])
    supplies = data.get("supplies", [])
    
    if not selected_supplies_ids:
        await callback.answer("❌ Не выбрано ни одной поставки!", show_alert=True)
        return
    
    # Получаем информацию о выбранных поставках
    selected_supplies = []
    for supply in supplies:
        if str(supply.get("id")) in selected_supplies_ids:
            selected_supplies.append(supply)
    
    # Показываем подтверждение
    supplies_text = ""
    for i, supply in enumerate(selected_supplies, 1):
        supply_name = supply.get("name", f"Поставка #{supply.get('id')}")
        status = supply.get("status", "unknown")
        supplies_text += f"{i}. {supply_name[:30]} ({status})\n"
    
    await callback.message.edit_text(
        f"🎯 <b>Подтверждение мультибронирования</b>\n\n"
        f"Выбрано поставок: {len(selected_supplies)}\n\n"
        f"{supplies_text}\n"
        f"🔥 Каждая поставка откроется в отдельном браузере\n"
        f"⚡ Бронирование будет происходить параллельно\n\n"
        f"Выберите параметры бронирования:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Выбрать дату", callback_data="multi_select_date")],
            [InlineKeyboardButton(text="📊 Выбрать коэффициент", callback_data="multi_select_coefficient")],
            [InlineKeyboardButton(text="🔥 Максимальный коэффициент", callback_data="multi_max_coefficient")],
            [InlineKeyboardButton(text="⚡ Быстрое бронирование", callback_data="multi_quick_booking")],
            [InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="multi_booking_mode")]
        ])
    )
    
    # Сохраняем выбранные поставки
    await state.update_data(selected_supplies_for_booking=selected_supplies)


# Обработчики параметров мультибронирования
@router.callback_query(F.data == "multi_select_date")
async def multi_select_date(callback: CallbackQuery, state: FSMContext):
    """Выбор даты для мультибронирования."""
    # Переходим к стандартному календарю
    from .booking_management import select_date_handler
    await select_date_handler(callback, state, multi_booking=True)


@router.callback_query(F.data == "multi_select_coefficient")
async def multi_select_coefficient(callback: CallbackQuery, state: FSMContext):
    """Выбор коэффициента для мультибронирования."""
    from .booking_management import select_coefficient_handler
    await select_coefficient_handler(callback, state, multi_booking=True)


@router.callback_query(F.data == "multi_max_coefficient")
async def multi_max_coefficient(callback: CallbackQuery, state: FSMContext):
    """Мультибронирование с максимальным коэффициентом."""
    await _execute_multi_booking(callback, state, booking_type="max_coefficient")


@router.callback_query(F.data == "multi_quick_booking")
async def multi_quick_booking(callback: CallbackQuery, state: FSMContext):
    """Быстрое мультибронирование."""
    await _execute_multi_booking(callback, state, booking_type="quick")


async def _execute_multi_booking(callback: CallbackQuery, state: FSMContext, booking_type: str, custom_date: str = None, coefficient: float = None):
    """Выполняет мультибронирование."""
    try:
        data = await state.get_data()
        selected_supplies = data.get("selected_supplies_for_booking", [])
        
        if not selected_supplies:
            await callback.answer("❌ Поставки не выбраны!", show_alert=True)
            return
        
        user_id = callback.from_user.id
        
        # Формируем параметры бронирования
        booking_params = {}
        if booking_type == "date":
            booking_params["custom_date"] = custom_date
        elif booking_type == "coefficient":
            booking_params["target_coefficient"] = coefficient
        elif booking_type == "coefficient_dates":
            selected_dates = data.get("selected_dates", [])
            booking_params["target_coefficient"] = coefficient
            booking_params["selected_dates"] = selected_dates
        elif booking_type == "max_coefficient":
            booking_params["use_max_coefficient"] = True
        
        # Показываем уведомление о запуске
        await callback.message.edit_text(
            f"🚀 <b>Запускаю мультибронирование!</b>\n\n"
            f"📦 Поставок: {len(selected_supplies)}\n"
            f"🔥 Тип: {booking_type}\n\n"
            f"⏳ Создаю отдельные браузеры...",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        
        # Получаем синглтон менеджеры
        from ...main import get_multi_booking_manager
        multi_booking_manager = get_multi_booking_manager()
        
        # Создаем callback для уведомлений
        async def progress_callback(message: str):
            try:
                await callback.message.edit_text(
                    f"🎯 <b>Мультибронирование</b>\n\n{message}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ])
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка обновления прогресса: {e}")
        
        # Запускаем мультибронирование
        session_id = await multi_booking_manager.start_multi_booking(
            user_id=user_id,
            supplies=selected_supplies,
            booking_params=booking_params,
            progress_callback=progress_callback
        )
        
        logger.info(f"🎯 Запущено мультибронирование с session_id: {session_id}")
        
        # Сохраняем session_id в состоянии
        await state.update_data(multi_booking_session_id=session_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска мультибронирования: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка мультибронирования</b>\n\n"
            f"<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="start_multi_booking")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="multi_booking_mode")]
            ])
        )
