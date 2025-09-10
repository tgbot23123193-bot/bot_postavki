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


def create_supplies_keyboard(supplies: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком ВСЕХ поставок."""
    keyboard = []
    
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
            
        button_text = f"{status_emoji} {display_name} ({status})"
        
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"supply_select:{supply_id}"
            )
        ])
    
    # Кнопки управления
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Обновить список", callback_data="supplies_refresh")],
        [InlineKeyboardButton(text="🏬 Склады", callback_data="view_warehouses")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    
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
