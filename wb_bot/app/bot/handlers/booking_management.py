"""
Обработчики для бронирования поставок
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from datetime import datetime, timedelta
from typing import List, Dict, Any
import asyncio

from ...utils.logger import get_logger
from ...utils.calendar_utils import TelegramCalendar, parse_calendar_callback
from ...services.wb_supplies_api import WBSuppliesAPIClient
from ...services.browser_manager import browser_manager
# Removed user_api_keys - using PostgreSQL database only

def escape_html(text: str) -> str:
    """Безопасное экранирование HTML символов."""
    if not text:
        return text
    # Экранируем все проблемные символы для HTML
    text = str(text)
    text = text.replace('&', '&amp;')  # Сначала &
    text = text.replace('<', '&lt;')   # Потом <
    text = text.replace('>', '&gt;')   # Потом >
    text = text.replace('"', '&quot;') # Кавычки
    text = text.replace("'", '&#39;')  # Одинарные кавычки
    return text

async def safe_edit_text(message, text, **kwargs):
    """Безопасное редактирование сообщения с обработкой ошибки 'message is not modified'."""
    try:
        await message.edit_text(text, **kwargs)
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.warning(f"⚠️ Ошибка редактирования сообщения: {e}")
            # Попробуем без HTML форматирования при ошибке parse entities
            if "can't parse entities" in str(e) and kwargs.get("parse_mode") == "HTML":
                try:
                    # Убираем HTML разметку и отправляем как обычный текст
                    import re
                    clean_text = re.sub(r'<[^>]+>', '', text)  # Убираем все HTML теги
                    kwargs_copy = kwargs.copy()
                    kwargs_copy.pop("parse_mode", None)
                    await message.edit_text(clean_text, **kwargs_copy)
                except Exception as e2:
                    logger.error(f"❌ Критическая ошибка отправки сообщения: {e2}")
from ..keyboards.inline import back_to_main_menu_keyboard

logger = get_logger(__name__)
router = Router()

# Глобальное хранилище мониторинга слотов
monitoring_sessions = {}


class BookingStates(StatesGroup):
    """Состояния для бронирования поставок."""
    selecting_warehouse = State()
    selecting_dates = State()
    confirming_booking = State()
    monitoring_slots = State()
    waiting_for_phone = State()
    waiting_for_sms_code = State()


def create_date_range_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора диапазона дат."""
    today = datetime.now()
    keyboard = []
    
    # Предустановленные диапазоны
    date_ranges = [
        ("📅 Сегодня", today, today),
        ("📅 Завтра", today + timedelta(days=1), today + timedelta(days=1)),
        ("📅 На неделю", today, today + timedelta(days=7)),
        ("📅 На месяц", today, today + timedelta(days=30))
    ]
    
    for text, date_from, date_to in date_ranges:
        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"date_range:{date_from.strftime('%Y-%m-%d')}:{date_to.strftime('%Y-%m-%d')}"
            )
        ])
    
    keyboard.extend([
        [InlineKeyboardButton(text="📝 Выбрать даты вручную", callback_data="custom_dates")],
        [InlineKeyboardButton(text="🤖 Автобронирование", callback_data="auto_book_supply")],
        [InlineKeyboardButton(text="⬅️ К поставке", callback_data="back_to_supply")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_warehouse_selection_keyboard(warehouses: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора склада."""
    keyboard = []
    
    for warehouse in warehouses[:10]:  # Показываем максимум 10 складов
        warehouse_id = warehouse.get("id", "")
        warehouse_name = warehouse.get("name", f"Склад #{warehouse_id}")
        
        # Обрезаем длинные названия
        display_name = warehouse_name[:40]
        if len(warehouse_name) > 40:
            display_name += "..."
            
        keyboard.append([
            InlineKeyboardButton(
                text=f"🏬 {display_name}",
                callback_data=f"select_warehouse:{warehouse_id}"
            )
        ])
    
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Показать все склады", callback_data="show_all_warehouses")],
        [InlineKeyboardButton(text="⬅️ К поставке", callback_data="back_to_supply")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data.startswith("book_supply:"))
async def start_booking_process(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс бронирования поставки."""
    supply_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные поставки из состояния
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    preorder_id = selected_supply.get("preorderId", supply_id)  # Берем preorderId если есть
    
    # Сохраняем данные для бронирования
    await state.update_data(
        booking_supply_id=supply_id,
        selected_supply=selected_supply
    )
    
    # Показываем меню выбора способа бронирования
    await callback.message.edit_text(
        f"🎯 <b>Бронирование поставки</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"🆔 ID поставки: <code>{supply_id}</code>\n"
        f"📋 ID заказа: <code>{preorder_id}</code>\n\n"
        f"Выберите способ бронирования:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🌐 Браузерное бронирование (рекомендуется)",
                callback_data=f"browser_book_supply:{supply_id}"
            )],
            [InlineKeyboardButton(
                text="🤖 Через API (выбор складов)",
                callback_data=f"api_book_supply:{supply_id}"
            )],
            [InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"supply_select:{supply_id}"
            )]
        ])
    )


@router.callback_query(F.data.startswith("api_book_supply:"))
async def api_book_supply(callback: CallbackQuery, state: FSMContext):
    """Бронирование через API с выбором складов."""
    supply_id = callback.data.split(":")[1]
    
    # Получаем данные поставки
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    
    await callback.message.edit_text(
        f"🤖 <b>Бронирование через API</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"🆔 ID: <code>{supply_id}</code>\n\n"
        f"📅 Выберите период для поиска слотов:",
        parse_mode="HTML",
        reply_markup=create_date_range_keyboard()
    )
    
    # Сохраняем ID поставки для бронирования
    await state.update_data(booking_supply_id=supply_id)
    await state.set_state(BookingStates.selecting_dates)


@router.callback_query(F.data == "custom_dates")
async def custom_date_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик ручного выбора дат."""
    await callback.message.edit_text(
        "📅 <b>Выбор дат вручную</b>\n\n"
        "Отправьте даты в формате: ГГГГ-ММ-ДД ГГГГ-ММ-ДД\n"
        "Например: 2025-09-10 2025-09-17\n\n"
        "Или выберите один из предложенных вариантов:",
        parse_mode="HTML",
        reply_markup=create_date_selection_keyboard()
    )
    await state.set_state(BookingStates.selecting_dates)


@router.callback_query(F.data.startswith("date_range:"))
async def process_date_range(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор диапазона дат."""
    _, date_from_str, date_to_str = callback.data.split(":")
    user_id = callback.from_user.id
    
    # Получаем API ключи пользователя из PostgreSQL
    from .callbacks import get_user_api_keys_list
    api_keys = await get_user_api_keys_list(user_id)
    if not api_keys:
        await callback.answer("❌ API ключ не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"⏳ <b>Загружаю список складов...</b>\n\n"
        f"📅 Период: {date_from_str} - {date_to_str}\n"
        f"Получаю данные о доступных складах...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем список складов и коэффициенты приёмки
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            warehouses = await api_client.get_warehouses()
            
            if warehouses:
                # Получаем коэффициенты приёмки для топ-25 складов (для бронирования)
                top_warehouses = warehouses[:25]
                warehouse_ids = [w.get("id") for w in top_warehouses if w.get("id")]
                available_slots = await api_client.get_acceptance_coefficients(warehouse_ids)
                logger.info(f"📊 Найдено доступных слотов: {len(available_slots)}")
            else:
                available_slots = []
            
        if not warehouses:
            await callback.message.edit_text(
                "❌ <b>Склады не найдены</b>\n\n"
                "Не удалось получить список доступных складов.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="back_to_supply")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ])
            )
            return
        
        # Фильтруем склады с доступными слотами
        warehouses_with_slots = []
        if available_slots:
            slot_warehouse_ids = set(slot.get("warehouseID") for slot in available_slots)
            warehouses_with_slots = [w for w in warehouses if w.get("id") in slot_warehouse_ids]
        
        if not warehouses_with_slots:
            await callback.message.edit_text(
                f"⚠️ <b>Нет доступных слотов</b>\n\n"
                f"📅 Период: {date_from_str} - {date_to_str}\n"
                f"❌ На выбранные даты нет доступных слотов для бронирования.\n\n"
                f"Попробуйте выбрать другие даты.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Другие даты", callback_data="back_to_supply")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ])
            )
            return
        
        # Показываем список складов с доступными слотами
        await callback.message.edit_text(
            f"🏬 <b>Выберите склад для бронирования</b>\n\n"
            f"📅 Период: {date_from_str} - {date_to_str}\n"
            f"📊 Доступно складов: {len(warehouses_with_slots)}\n"
            f"🎯 Найдено слотов: {len(available_slots)}\n\n"
            f"Выберите склад с доступными слотами:",
            parse_mode="HTML",
            reply_markup=create_warehouse_selection_keyboard(warehouses_with_slots)
        )
        
        # Сохраняем даты, склады и слоты в состоянии
        await state.update_data(
            date_from=date_from_str,
            date_to=date_to_str,
            warehouses=warehouses_with_slots,
            available_slots=available_slots
        )
        await state.set_state(BookingStates.selecting_warehouse)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения складов для пользователя {user_id}: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка получения складов</b>\n\n"
            f"Не удалось загрузить список складов:\n"
            f"<code>{escape_html(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="back_to_supply")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )


@router.callback_query(F.data == "back_to_supply")
async def back_to_supply_handler(callback: CallbackQuery, state: FSMContext):
    """Возвращает к выбранной поставке."""
    # Получаем данные из состояния
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        # Если нет выбранной поставки, возвращаемся к списку
        await callback.message.edit_text(
            "⬅️ Возвращаемся к списку поставок...",
            parse_mode="HTML"
        )
        # Вызываем обработчик списка поставок
        from .supplies_management import show_supplies_menu
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


@router.callback_query(F.data == "auto_book_supply")
async def auto_book_supply_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает кнопку автобронирования."""
    # Получаем данные из состояния
    data = await state.get_data()
    booking_supply_id = data.get("booking_supply_id")
    
    if not booking_supply_id:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    # Перенаправляем на браузерное бронирование с дефолтными датами
    await state.update_data(
        date_from="2025-09-07",
        date_to="2025-09-14"
    )
    
    # Вызываем обработчик браузерного бронирования напрямую
    from aiogram.types import CallbackQuery
    
    # Создаем новый callback с правильными данными
    new_callback = CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        message=callback.message,
        data=f"browser_book_supply:{booking_supply_id}",
        chat_instance=callback.chat_instance
    )
    
    await browser_book_supply(new_callback, state)


@router.callback_query(F.data.startswith("browser_book_supply:"))
async def browser_book_supply(callback: CallbackQuery, state: FSMContext):
    """Бронирует поставку через браузер."""
    supply_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    
    # Получаем preorderId - проверяем разные варианты написания
    preorder_id = selected_supply.get("preorderId") or selected_supply.get("preorderID") or selected_supply.get("preorder_id")
    
    # Если preorderId не найден, используем сам supply_id
    if not preorder_id:
        logger.warning(f"⚠️ preorderId не найден для поставки {supply_id}, используем supply_id")
        preorder_id = supply_id
    
    # Показываем варианты бронирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Выбрать дату", callback_data=f"select_date_{supply_id}_{preorder_id}")],
        [InlineKeyboardButton(text="💰 Выбрать коэффициент", callback_data=f"select_coefficient_{supply_id}_{preorder_id}")],
        [InlineKeyboardButton(text="📊 Максимальный коэффициент", callback_data=f"max_coeff_{supply_id}_{preorder_id}")],
        [InlineKeyboardButton(text="⚡ Быстрое бронирование (через 3 дня)", callback_data=f"quick_book_{supply_id}_{preorder_id}")],
        [InlineKeyboardButton(text="🔙 Назад к поставкам", callback_data="view_supplies")]
    ])
    
    await safe_edit_text(
        callback.message,
        f"📦 <b>ВАРИАНТЫ БРОНИРОВАНИЯ</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"🆔 ID: <code>{supply_id}</code>\n"
        f"📋 Заказ: <code>{preorder_id}</code>\n\n"
        f"🎯 <b>Выберите способ бронирования:</b>\n\n"
        f"📅 <b>Выбрать дату</b> - Укажите конкретную дату\n"
        f"💰 <b>Выбрать коэффициент</b> - Выберите коэффициент от 1 до 20 или бесплатно\n"
        f"📊 <b>Максимальный коэффициент</b> - Автоматически найдем лучший коэффициент\n"
        f"⚡ <b>Быстрое бронирование</b> - Стандартно через 3 дня",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# Обработчик быстрого бронирования (через 3 дня)
@router.callback_query(F.data.startswith("quick_book_"))
async def quick_book_handler(callback: CallbackQuery, state: FSMContext):
    """Быстрое бронирование поставки через 3 дня."""
    parts = callback.data.split("_")
    supply_id = parts[2]
    preorder_id = parts[3]
    
    await _execute_booking(callback, state, supply_id, preorder_id, "quick")


# Обработчик бронирования с максимальным коэффициентом
@router.callback_query(F.data.startswith("max_coeff_"))
async def max_coeff_handler(callback: CallbackQuery, state: FSMContext):
    """Бронирование поставки с максимальным коэффициентом."""
    parts = callback.data.split("_")
    supply_id = parts[2]
    preorder_id = parts[3]
    
    await _execute_booking(callback, state, supply_id, preorder_id, "max_coeff")


# Обработчик выбора коэффициента (показ меню)
@router.callback_query(F.data.startswith("select_coefficient_"))
async def select_coefficient_handler(callback: CallbackQuery, state: FSMContext, multi_booking: bool = False):
    """Показывает меню выбора коэффициента."""
    if not multi_booking:
        parts = callback.data.split("_")
        supply_id = parts[2]
        preorder_id = parts[3]
        
        # Сохраняем данные в состояние
        await state.update_data({
            "booking_supply_id": supply_id,
            "booking_preorder_id": preorder_id
        })
    else:
        supply_id = "multi"
        preorder_id = "multi"
    
    # Создаем клавиатуру с коэффициентами 1-20
    keyboard = []
    
    # Добавляем кнопки для коэффициентов 1-10 (по 5 в ряду)
    for row_start in range(1, 11, 5):
        row = []
        for coeff in range(row_start, min(row_start + 5, 11)):
            row.append(InlineKeyboardButton(
                text=f"📊 {coeff}",
                callback_data=f"coeff_select_{coeff}_{supply_id}_{preorder_id}"
            ))
        keyboard.append(row)
    
    # Добавляем кнопки для коэффициентов 11-20 (по 5 в ряду)
    for row_start in range(11, 21, 5):
        row = []
        for coeff in range(row_start, min(row_start + 5, 21)):
            row.append(InlineKeyboardButton(
                text=f"📊 {coeff}",
                callback_data=f"coeff_select_{coeff}_{supply_id}_{preorder_id}"
            ))
        keyboard.append(row)
    
    # Специальная кнопка для бесплатной брони (коэффициент 0)
    keyboard.append([
        InlineKeyboardButton(
            text="🆓 Бесплатная бронь",
            callback_data=f"coeff_select_0_{supply_id}_{preorder_id}"
        )
    ])
    
    # Кнопка назад
    if multi_booking:
        keyboard.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="start_multi_booking")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"book_supply:{supply_id}")
        ])
    
    title = "🎯 Выбор коэффициента для мультибронирования" if multi_booking else "📊 Выбор коэффициента"
    
    await callback.message.edit_text(
        f"{title}\n\n"
        f"Выберите максимальный коэффициент приёмки:\n"
        f"• Бот найдет дату с коэффициентом ≤ выбранного\n"
        f"• Чем меньше коэффициент, тем дешевле\n"
        f"• 🆓 Бесплатная бронь = коэффициент 0",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


# Обработчик выбора даты (показ календаря)
@router.callback_query(F.data.startswith("select_date_"))
async def select_date_handler(callback: CallbackQuery, state: FSMContext, multi_booking: bool = False):
    """Показывает календарь для выбора даты бронирования."""
    if not multi_booking:
        parts = callback.data.split("_")
        supply_id = parts[2]  
        preorder_id = parts[3]
        
        # Сохраняем данные в состояние
        await state.update_data({
            "booking_supply_id": supply_id,
            "booking_preorder_id": preorder_id
        })
    else:
        # Для мультибронирования не нужен конкретный supply_id
        supply_id = "multi"
        preorder_id = "multi"
    
    # Показываем календарь текущего месяца
    current_date = datetime.now()
    calendar_markup = TelegramCalendar.create_calendar(
        year=current_date.year,
        month=current_date.month,
        supply_id=supply_id,
        preorder_id=preorder_id
    )
    
    calendar_text = TelegramCalendar.get_calendar_text(
        year=current_date.year,
        month=current_date.month
    )
    
    if multi_booking:
        calendar_text = f"🎯 <b>Выбор даты для мультибронирования</b>\n\n{calendar_text}"
    
    await callback.message.edit_text(
        calendar_text,
        parse_mode="HTML",
        reply_markup=calendar_markup
    )


# Обработчики календаря
@router.callback_query(F.data.startswith("calendar_"))
async def calendar_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает действия с календарем."""
    callback_data = callback.data
    parsed = parse_calendar_callback(callback_data)
    
    if not parsed or parsed[0] == "ignore":
        # Игнорируем клики на заголовки и пустые дни
        await callback.answer()
        return
    
    action_type = parsed[0]
    
    if action_type == "nav":
        # Навигация по месяцам
        if len(parsed) >= 5:
            year, month, supply_id, preorder_id = parsed[1], parsed[2], parsed[3], parsed[4]
            
            # Обновляем календарь на новый месяц
            calendar_markup = TelegramCalendar.create_calendar(
                year=year,
                month=month,
                supply_id=supply_id,
                preorder_id=preorder_id
            )
            
            calendar_text = TelegramCalendar.get_calendar_text(year=year, month=month)
            
            await callback.message.edit_text(
                calendar_text,
                parse_mode="HTML",
                reply_markup=calendar_markup
            )
            await callback.answer()
    
    elif action_type == "select":
        # Выбор даты
        if len(parsed) >= 4:
            selected_date, supply_id, preorder_id = parsed[1], parsed[2], parsed[3]
            
            # Добавляем дату в список выбранных дат в состоянии (без дубликатов)
            data = await state.get_data()
            selected_dates = data.get("selected_dates", [])
            if selected_date not in selected_dates:
                selected_dates.append(selected_date)
            await state.update_data(selected_dates=selected_dates, supply_id=supply_id, preorder_id=preorder_id)
            
            # Текст со списком выбранных дат
            dates_text = "\n".join([f"• {d}" for d in selected_dates]) if selected_dates else "—"
            
            # Кнопки: добавить еще дату, выбрать коэффициент, очистить, назад
            next_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="➕ Добавить еще дату",
                    callback_data=f"select_date_{supply_id}_{preorder_id}"
                )],
                [InlineKeyboardButton(
                    text="💰 Выбрать коэффициент",
                    callback_data=f"coeff_after_dates_{supply_id}_{preorder_id}"
                )],
                [InlineKeyboardButton(
                    text="🧹 Очистить выбор",
                    callback_data=f"clear_dates_{supply_id}_{preorder_id}"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад к вариантам",
                    callback_data=f"browser_book_supply:{supply_id}"
                )]
            ])
            
            await callback.message.edit_text(
                f"📅 <b>ВЫБРАННЫЕ ДАТЫ</b>\n\n"
                f"🆔 Поставка: <code>{supply_id}</code>\n"
                f"📋 Заказ: <code>{preorder_id}</code>\n\n"
                f"📅 <b>Список дат:</b>\n{dates_text}\n\n"
                f"Вы можете добавить еще даты или перейти к выбору коэффициента.",
                parse_mode="HTML",
                reply_markup=next_keyboard
            )
            await callback.answer("Дата добавлена")
    
    else:
        await callback.answer()


# Обработчик очистки выбранных дат
@router.callback_query(F.data.startswith("clear_dates_"))
async def clear_dates_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    supply_id = parts[2]
    preorder_id = parts[3]
    
    await state.update_data(selected_dates=[])
    
    await callback.message.edit_text(
        f"🧹 Выбор дат очищен.\n\n"
        f"Нажмите, чтобы выбрать даты заново:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Открыть календарь", callback_data=f"select_date_{supply_id}_{preorder_id}")],
            [InlineKeyboardButton(text="🔙 Назад к вариантам", callback_data=f"browser_book_supply:{supply_id}")]
        ]),
        parse_mode="HTML"
    )


# Обработчик показа меню коэффициента ПОСЛЕ выбора дат
@router.callback_query(F.data.startswith("coeff_after_dates_"))
async def coeff_after_dates_handler(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    supply_id = parts[3]
    preorder_id = parts[4]
    
    data = await state.get_data()
    selected_dates = data.get("selected_dates", [])
    if not selected_dates:
        await callback.answer("Сначала выберите даты", show_alert=True)
        return
    
    # Создаем клавиатуру с коэффициентами (0-20)
    keyboard_buttons = []
    keyboard_buttons.append([InlineKeyboardButton(
        text="🆓 Бесплатно (0)",
        callback_data=f"coeff_select_0_{supply_id}_{preorder_id}"
    )])
    coeff_buttons = []
    for i in range(1, 21):
        coeff_buttons.append(InlineKeyboardButton(
            text=f"{i}",
            callback_data=f"coeff_select_{i}_{supply_id}_{preorder_id}"
        ))
        if len(coeff_buttons) == 5:
            keyboard_buttons.append(coeff_buttons)
            coeff_buttons = []
    if coeff_buttons:
        keyboard_buttons.append(coeff_buttons)
    keyboard_buttons.append([InlineKeyboardButton(
        text="🔙 Назад к датам",
        callback_data=f"select_date_{supply_id}_{preorder_id}"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    dates_text = ", ".join(selected_dates)
    await callback.message.edit_text(
        f"💰 <b>ВЫБОР КОЭФФИЦИЕНТА</b>\n\n"
        f"📦 <b>Поставка:</b> <code>{supply_id}</code>\n"
        f"📋 <b>Заказ:</b> <code>{preorder_id}</code>\n"
        f"📅 <b>Даты:</b> {dates_text}\n\n"
        f"Выберите коэффициент, он будет проверяться ТОЛЬКО на выбранных датах.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# Обработчик выбора конкретного коэффициента
@router.callback_query(F.data.startswith("coeff_select_"))
async def coefficient_selected_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор конкретного коэффициента."""
    parts = callback.data.split("_")
    coefficient = float(parts[2])
    supply_id = parts[3]
    preorder_id = parts[4]
    
    # Проверяем это мультибронирование или обычное
    if supply_id == "multi" and preorder_id == "multi":
        # Мультибронирование - вызываем функцию из supplies_management
        from .supplies_management import _execute_multi_booking
        data = await state.get_data()
        selected_dates = data.get("selected_dates", [])
        
        if selected_dates:
            await _execute_multi_booking(
                callback, state, "coefficient_dates", coefficient=coefficient
            )
        else:
            await _execute_multi_booking(
                callback, state, "coefficient", coefficient=coefficient
            )
    else:
        # Обычное бронирование одной поставки
        data = await state.get_data()
        selected_dates = data.get("selected_dates", [])
        
        if selected_dates:
            # Если выбраны даты — бронируем по датам с указанным коэффициентом
            await _execute_booking(
                callback, state, supply_id, preorder_id,
                "coefficient_dates", custom_date=None, coefficient=coefficient
            )
        else:
            # Иначе — старый сценарий (поиск даты с коэффициентом)
            await _execute_booking(
                callback, state, supply_id, preorder_id,
                "coefficient", custom_date=None, coefficient=coefficient
            )


# Обработчик подтверждения выбранной даты
@router.callback_query(F.data.startswith("confirm_date_"))
async def confirm_date_handler(callback: CallbackQuery, state: FSMContext):
    """Подтверждает выбранную дату и запускает бронирование."""
    parts = callback.data.split("_")
    selected_date = parts[2]  # DD.MM.YYYY
    supply_id = parts[3]
    preorder_id = parts[4]
    
    # НЕ ОЧИЩАЕМ СОСТОЯНИЕ! Нужны данные поставки!
    # await state.clear()  # УБИРАЮ ЭТУ СТРОКУ!
    
    # Запускаем бронирование с выбранной датой
    await _execute_booking(callback, state, supply_id, preorder_id, "custom", selected_date)


# Обработчик ввода кастомной даты (оставляем для совместимости)
@router.message(F.text, StateFilter("waiting_for_custom_date"))
async def process_custom_date(message: Message, state: FSMContext):
    """Обрабатывает введенную пользователем дату."""
    user_date = message.text.strip()
    data = await state.get_data()
    supply_id = data.get("booking_supply_id")
    preorder_id = data.get("booking_preorder_id")
    
    if not supply_id or not preorder_id:
        await message.answer("❌ Ошибка: данные поставки не найдены. Начните сначала.")
        await state.clear()
        return
    
    # Проверяем формат даты
    try:
        from datetime import datetime, timedelta
        
        # Пробуем различные форматы
        formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y']
        parsed_date = None
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(user_date, fmt)
                break
            except ValueError:
                continue
        
        if not parsed_date:
            await message.answer(
                f"❌ <b>Неверный формат даты!</b>\n\n"
                f"🔍 Вы ввели: <code>{user_date}</code>\n\n"
                f"📝 Используйте один из форматов:\n"
                f"• DD.MM.YYYY (например: 20.09.2024)\n"
                f"• DD/MM/YYYY (например: 20/09/2024)\n"
                f"• DD-MM-YYYY (например: 20-09-2024)",
                parse_mode="HTML"
            )
            return
        
        # Проверяем что дата не в прошлом
        tomorrow = datetime.now() + timedelta(days=1)
        if parsed_date.date() < tomorrow.date():
            await message.answer(
                f"❌ <b>Дата слишком ранняя!</b>\n\n"
                f"🔍 Вы выбрали: <code>{parsed_date.strftime('%d.%m.%Y')}</code>\n"
                f"📅 Минимальная дата: <code>{tomorrow.strftime('%d.%m.%Y')}</code>\n\n"
                f"⚠️ Выберите дату не раньше завтрашнего дня.",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем дату и переходим к бронированию
        await state.update_data({"custom_date": user_date})
        await state.clear()
        
        # Создаем фейковый callback для вызова бронирования
        fake_callback = type('FakeCallback', (), {
            'message': message,
            'from_user': message.from_user,
            'data': f"custom_date_{supply_id}_{preorder_id}"
        })()
        
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except:
            pass
        
        await _execute_booking(fake_callback, state, supply_id, preorder_id, "custom", user_date)
        
    except Exception as e:
        logger.error(f"Ошибка обработки даты: {e}")
        await message.answer(
            f"❌ Ошибка обработки даты. Попробуйте еще раз.",
            parse_mode="HTML"
        )


# Универсальная функция бронирования
async def _execute_booking(callback, state: FSMContext, supply_id: str, preorder_id: str, booking_type: str, custom_date: str = None, coefficient: float = None):
    """Выполняет бронирование поставки с выбранными параметрами."""
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        # Если данные поставки не найдены в состоянии, попробуем найти через API
        logger.warning(f"⚠️ Данные поставки не найдены в состоянии для supply_id: {supply_id}")
        
        try:
            # Получаем API ключи пользователя
            from ...services.database_service import DatabaseService
            db_service = DatabaseService()
            api_keys = await db_service.get_decrypted_api_keys(user_id)
            
            if api_keys:
                api_key = api_keys[0]  # Берем первый ключ
                wb_api = WBSuppliesAPIClient(api_key)
                supplies = await wb_api.get_supplies()
                
                # Ищем нужную поставку
                found_supply = None
                for supply in supplies:
                    if str(supply.get('id')) == str(supply_id) or str(supply.get('preorderID')) == str(preorder_id):
                        found_supply = supply
                        break
                
                if found_supply:
                    selected_supply = found_supply
                    logger.info(f"✅ Найдена поставка через API: {found_supply}")
                    # Сохраняем в состояние для дальнейшего использования
                    await state.update_data({"selected_supply": selected_supply})
                else:
                    await safe_edit_text(callback.message, f"❌ Поставка {supply_id} не найдена через API", parse_mode="HTML")
                    return
            else:
                await safe_edit_text(callback.message, "❌ API ключи не найдены", parse_mode="HTML")
                return
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска поставки через API: {e}")
            await safe_edit_text(callback.message, f"❌ Ошибка поиска поставки: {str(e).replace('<', '&lt;').replace('>', '&gt;')}", parse_mode="HTML")
            return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    
    # Определяем тип бронирования для отображения
    booking_type_text = {
        "quick": "⚡ Быстрое бронирование (через 3 дня)",
        "max_coeff": "📊 Максимальный коэффициент",
        "custom": f"📅 Кастомная дата: {custom_date}"
    }.get(booking_type, "🤖 Автоматическое бронирование")
    
    await safe_edit_text(
        callback.message,
        f"🤖 <b>Запускаю бронирование...</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"🆔 ID: <code>{supply_id}</code>\n"
        f"📋 Заказ: <code>{preorder_id}</code>\n"
        f"🎯 Режим: {booking_type_text}\n\n"
        f"⏳ Открываю браузер и выполняю вход...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем браузер через единый менеджер
        browser = await browser_manager.get_browser(user_id, headless=False, debug_mode=True)
        
        if not browser or not browser.page:
            await callback.message.edit_text(
                f"❌ <b>Ошибка получения браузера</b>\n\n"
                f"Не удалось получить экземпляр браузера для автоматизации.\n"
                f"Браузер: {browser is not None}\n"
                f"Страница: {browser.page is not None if browser else False}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            return
        
        # Проверяем есть ли валидная сессия
        should_skip_login = await browser.should_skip_login()
        if should_skip_login:
            await callback.message.edit_text(
                f"✅ <b>Найдена сохраненная сессия!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"🔄 Запускаю браузер с сохраненной авторизацией...",
                parse_mode="HTML"
            )
        
        # Браузер уже запущен через browser_manager, проверяем его состояние
        if not browser.page or browser.page.is_closed():
            await callback.message.edit_text(
                f"❌ <b>Ошибка состояния браузера</b>\n\n"
                f"Браузер не готов к работе.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            return
        
        # Проверяем авторизацию (если не пропускали ранее)
        if not should_skip_login:
            await callback.message.edit_text(
                f"🤖 <b>Браузер запущен!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"🔍 Проверяю авторизацию...",
                parse_mode="HTML"
            )
            
            # Проверяем, авторизован ли пользователь
            is_logged_in = await browser.check_if_logged_in()
        else:
            # Если сессия была валидна, считаем что пользователь авторизован
            is_logged_in = True
            await callback.message.edit_text(
                f"✅ <b>Авторизация подтверждена!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"🎯 Переходим к бронированию поставки...",
                parse_mode="HTML"
            )
        
        if not is_logged_in:
            # Если не авторизован - начинаем процесс логина
            await callback.message.edit_text(
                f"🔐 <b>Требуется авторизация</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"📱 Введите номер телефона для входа в WB:\n"
                f"(в формате +79991234567 или +996500441234)",
                parse_mode="HTML"
            )
            
            # Сохраняем данные поставки в состоянии
            await state.update_data(
                supply_id=supply_id,
                supply_name=supply_name,
                preorder_id=preorder_id,
                selected_supply=selected_supply
            )
            await state.set_state(BookingStates.waiting_for_phone)
            return
        
        # Обновляем статус
        await callback.message.edit_text(
            f"✅ <b>Вход выполнен!</b>\n\n"
            f"📦 <b>{supply_name}</b>\n"
            f"⏳ Ищу поставку и бронирую слот...",
            parse_mode="HTML"
        )
        
        # Выполняем бронирование поставки с выбранными параметрами
        if booking_type == "quick":
            # Быстрое бронирование через 3 дня
            booking_result = await browser.book_supply_by_id(
                supply_id=str(supply_id),
                preorder_id=str(preorder_id),
                min_hours_ahead=80
            )
        elif booking_type == "max_coeff":
            # Бронирование с максимальным коэффициентом
            booking_result = await browser.book_supply_by_id(
                supply_id=str(supply_id),
                preorder_id=str(preorder_id),
                min_hours_ahead=80,
                use_max_coefficient=True
            )
        elif booking_type == "custom":
            # Бронирование на кастомную дату
            booking_result = await browser.book_supply_by_id(
                supply_id=str(supply_id),
                preorder_id=str(preorder_id),
                min_hours_ahead=80,
                custom_date=custom_date
            )
        elif booking_type == "coefficient":
            # Бронирование с конкретным коэффициентом
            booking_result = await browser.book_supply_by_id(
                supply_id=str(supply_id),
                preorder_id=str(preorder_id),
                min_hours_ahead=80,
                target_coefficient=coefficient
            )
        elif booking_type == "coefficient_dates":
            # Бронирование по списку выбранных дат с указанным коэффициентом
            data = await state.get_data()
            selected_dates = data.get("selected_dates", [])
            
            if not selected_dates:
                booking_result = {"success": False, "message": "❌ Даты не выбраны"}
            else:
                # Передаем весь список дат в browser_automation для умной обработки
                booking_result = await browser.book_supply_by_id(
                    supply_id=str(supply_id),
                    preorder_id=str(preorder_id),
                    min_hours_ahead=80,
                    target_coefficient=coefficient,
                    selected_dates=selected_dates
                )
        else:
            # По умолчанию - быстрое бронирование
            booking_result = await browser.book_supply_by_id(
                supply_id=str(supply_id),
                preorder_id=str(preorder_id),
                min_hours_ahead=80
            )
        
        booking_success = booking_result["success"]
        booking_message = booking_result["message"]
        booked_date = booking_result.get("booked_date")
        
        # ПОЛУЧАЕМ ДЕТАЛИ БРОНИРОВАНИЯ
        booking_date = booking_result.get("booking_date", "Неизвестно")
        warehouse_name = booking_result.get("warehouse_name", "Неизвестен")
        coefficient = booking_result.get("coefficient", "Неизвестен")
        new_supply_id = booking_result.get("new_supply_id")
        
        # НЕ закрываем браузер - оставляем его открытым для пользователя
        # await browser.close_browser()
        
        if booking_success:
            # Формируем сообщение с учетом нового ID
            message_text = (
                f"🎉 <b>ПОСТАВКА УСПЕШНО ЗАБРОНИРОВАНА!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"🆔 Старый ID: <code>{supply_id}</code>\n"
                f"📋 Заказ: <code>{preorder_id}</code>\n"
            )
            
            # Добавляем новый ID если найден
            if new_supply_id and new_supply_id != str(supply_id):
                message_text += f"🆔 <b>Новый ID поставки:</b> <code>{new_supply_id}</code>\n"
            
            message_text += (
                f"\n📅 <b>Дата поставки:</b> {booking_date}\n"
                f"🏬 <b>Склад:</b> {warehouse_name}\n"
                f"📊 <b>Коэффициент:</b> {coefficient}\n\n"
                f"✅ {escape_html(booking_message)}"
            )
            
            await callback.message.edit_text(
                message_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 К поставкам", callback_data="view_supplies")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
        else:
            # Проверяем тип ошибки
            if "Не авторизован" in booking_message:
                error_text = (
                    f"🔐 <b>Требуется авторизация</b>\n\n"
                    f"📦 <b>{supply_name}</b>\n"
                    f"❌ {escape_html(booking_message)}\n\n"
                    f"Сначала войдите в аккаунт WB через браузерное бронирование."
                )
                buttons = [
                    [InlineKeyboardButton(text="🔐 Войти в аккаунт", callback_data="browser_booking")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ]
            elif "попыток" in booking_message.lower():
                error_text = (
                    f"⚠️ <b>Бронирование не удалось</b>\n\n"
                    f"📦 <b>{supply_name}</b>\n"
                    f"🔄 Попытки: {booking_result.get('attempts', 0)}\n"
                    f"❌ {escape_html(booking_message)}\n\n"
                    f"Попробуйте позже или выберите другие параметры."
                )
                buttons = [
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ]
            else:
                error_text = (
                    f"⚠️ <b>Бронирование не удалось</b>\n\n"
                    f"📦 <b>{supply_name}</b>\n"
                    f"❌ {escape_html(booking_message)}\n\n"
                    f"Попробуйте позже или обратитесь в поддержку."
                )
                buttons = [
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ]
            
            await callback.message.edit_text(
                error_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        
    except Exception as e:
        logger.error(f"❌ Ошибка автоматического бронирования: {e}")
        
        # Очищаем текст ошибки от HTML тегов
        import html
        error_text = html.escape(str(e))
        
        await callback.message.edit_text(
            f"❌ <b>Ошибка бронирования</b>\n\n"
            f"📦 <b>{supply_name}</b>\n"
            f"💥 Произошла ошибка: <code>{error_text}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
            ])
        )


@router.callback_query(F.data.startswith("select_warehouse:"))
async def select_warehouse_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбирает склад для бронирования."""
    warehouse_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    warehouses = data.get("warehouses", [])
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    booking_supply_id = data.get("booking_supply_id")
    selected_supply = data.get("selected_supply")
    
    # Находим выбранный склад
    selected_warehouse = None
    for warehouse in warehouses:
        if str(warehouse.get("id")) == warehouse_id:
            selected_warehouse = warehouse
            break
    
    if not selected_warehouse:
        await callback.answer("❌ Склад не найден", show_alert=True)
        return
    
    warehouse_name = selected_warehouse.get("name", f"Склад #{warehouse_id}")
    supply_name = selected_supply.get("name", f"Поставка #{booking_supply_id}")
    
    await callback.message.edit_text(
        f"🎯 <b>Подтверждение бронирования</b>\n\n"
        f"📦 <b>Поставка:</b> {supply_name}\n"
        f"🏬 <b>Склад:</b> {warehouse_name}\n"
        f"📅 <b>Период:</b> {date_from} - {date_to}\n\n"
        f"Выберите режим бронирования:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Автобронирование", callback_data=f"auto_book:{warehouse_id}")],
            [InlineKeyboardButton(text="👁‍🗨 Мониторинг слотов", callback_data=f"monitor_slots:{warehouse_id}")],
            [InlineKeyboardButton(text="🔍 Проверить слоты сейчас", callback_data=f"check_slots:{warehouse_id}")],
            [InlineKeyboardButton(text="⬅️ Выбрать другой склад", callback_data=f"date_range:{date_from}:{date_to}")]
        ])
    )
    
    # Сохраняем выбранный склад
    await state.update_data(
        selected_warehouse=selected_warehouse,
        selected_warehouse_id=warehouse_id
    )


@router.callback_query(F.data.startswith("auto_book:"))
async def start_auto_booking(callback: CallbackQuery, state: FSMContext):
    """Запускает автобронирование."""
    warehouse_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    booking_supply_id = data.get("booking_supply_id")
    selected_supply = data.get("selected_supply")
    selected_warehouse = data.get("selected_warehouse")
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    
    supply_name = selected_supply.get("name", f"Поставка #{booking_supply_id}")
    warehouse_name = selected_warehouse.get("name", f"Склад #{warehouse_id}")
    
    await callback.message.edit_text(
        f"🤖 <b>Автобронирование запущено!</b>\n\n"
        f"📦 <b>Поставка:</b> {supply_name}\n"
        f"🏬 <b>Склад:</b> {warehouse_name}\n"
        f"📅 <b>Период:</b> {date_from} - {date_to}\n\n"
        f"⏳ Инициализирую браузер для бронирования...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем браузер через единый менеджер (видимый для отладки)
        browser = await browser_manager.get_browser(user_id, headless=False, debug_mode=True)
        
        if not browser:
            raise Exception("Не удалось запустить браузер")
        
        # Сохраняем данные для автобронирования
        monitoring_sessions[user_id] = {
            "supply_id": booking_supply_id,
            "warehouse_id": warehouse_id,
            "date_from": date_from,
            "date_to": date_to,
            "status": "active"
        }
        
        await callback.message.edit_text(
            f"✅ <b>Автобронирование активно!</b>\n\n"
            f"📦 <b>Поставка:</b> {supply_name}\n"
            f"🏬 <b>Склад:</b> {warehouse_name}\n"
            f"📅 <b>Период:</b> {date_from} - {date_to}\n\n"
            f"🔄 Бот будет проверять слоты каждые 30 секунд\n"
            f"📬 Уведомления приходят автоматически\n\n"
            f"<i>Для остановки используйте кнопку ниже</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏹ Остановить автобронирование", callback_data=f"stop_auto_book:{user_id}")],
                [InlineKeyboardButton(text="📊 Статус", callback_data=f"booking_status:{user_id}")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )
        
        # Запускаем фоновую задачу автобронирования
        asyncio.create_task(auto_booking_task(user_id, callback.bot))
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска автобронирования: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка автобронирования</b>\n\n"
            f"Не удалось запустить автобронирование:\n"
            f"<code>{escape_html(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"auto_book:{warehouse_id}")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )


@router.callback_query(F.data.startswith("check_slots:"))
async def check_available_slots(callback: CallbackQuery, state: FSMContext):
    """Проверяет доступные слоты прямо сейчас."""
    warehouse_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    selected_warehouse = data.get("selected_warehouse")
    
    warehouse_name = selected_warehouse.get("name", f"Склад #{warehouse_id}")
    
    await callback.message.edit_text(
        f"🔍 <b>Проверяю слоты...</b>\n\n"
        f"🏬 <b>Склад:</b> {warehouse_name}\n"
        f"📅 <b>Период:</b> {date_from} - {date_to}\n\n"
        f"⏳ Запрашиваю данные из API WB...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем API ключ пользователя из PostgreSQL
        from .callbacks import get_user_api_keys_list
        api_keys = await get_user_api_keys_list(user_id)
        if not api_keys:
            await callback.message.edit_text(
                "❌ API ключ не найден",
                reply_markup=back_to_main_menu_keyboard()
            )
            return
        
        # Проверяем доступные слоты
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            slots = await api_client.get_available_slots(
                warehouse_id=int(warehouse_id),
                date_from=date_from,
                date_to=date_to
            )
        
        if not slots:
            await callback.message.edit_text(
                f"📭 <b>Слоты не найдены</b>\n\n"
                f"🏬 <b>Склад:</b> {warehouse_name}\n"
                f"📅 <b>Период:</b> {date_from} - {date_to}\n\n"
                f"❌ На выбранный период нет доступных слотов\n"
                f"Попробуйте выбрать другие даты или склад.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👁‍🗨 Мониторить появление", callback_data=f"monitor_slots:{warehouse_id}")],
                    [InlineKeyboardButton(text="📅 Выбрать другие даты", callback_data="back_to_supply")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ])
            )
            return
        
        # Формируем сообщение со слотами
        slots_text = ""
        for i, slot in enumerate(slots[:5]):  # Показываем первые 5 слотов
            date = slot.get("date", "")
            coefficient = slot.get("coefficient", 0)
            slots_text += f"📅 {date} - коэффициент {coefficient}x\n"
        
        if len(slots) > 5:
            slots_text += f"\n... и еще {len(slots) - 5} слотов"
        
        await callback.message.edit_text(
            f"✅ <b>Найдены доступные слоты!</b>\n\n"
            f"🏬 <b>Склад:</b> {warehouse_name}\n"
            f"📊 <b>Всего слотов:</b> {len(slots)}\n\n"
            f"{slots_text}\n\n"
            f"Что делать дальше?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤖 Забронировать автоматически", callback_data=f"auto_book:{warehouse_id}")],
                [InlineKeyboardButton(text="👁‍🗨 Мониторить изменения", callback_data=f"monitor_slots:{warehouse_id}")],
                [InlineKeyboardButton(text="🔄 Обновить список", callback_data=f"check_slots:{warehouse_id}")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки слотов: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка проверки слотов</b>\n\n"
            f"Не удалось получить данные о слотах:\n"
            f"<code>{escape_html(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"check_slots:{warehouse_id}")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )


async def auto_booking_task(user_id: int, bot):
    """Фоновая задача автобронирования."""
    session = monitoring_sessions.get(user_id)
    if not session:
        return
    
    # Получаем браузер через единый менеджер (видимый для отладки мониторинга)
    browser = await browser_manager.get_browser(user_id, headless=False, debug_mode=True)
    if not browser:
        logger.error(f"❌ Не удалось получить браузер для пользователя {user_id}")
        return
    
    supply_id = session["supply_id"]
    warehouse_id = session["warehouse_id"]
    date_from = session["date_from"]
    date_to = session["date_to"]
    
    logger.info(f"🤖 Запущено автобронирование для пользователя {user_id}")
    
    try:
        while session.get("status") == "active":
            # Проверяем слоты через API
            user = await get_user_by_telegram_id(user_id)
            if not user or not user.api_key:
                break
                
            async with WBSuppliesAPIClient(api_keys[0]) as api_client:
                slots = await api_client.get_available_slots(
                    warehouse_id=int(warehouse_id),
                    date_from=date_from,
                    date_to=date_to
                )
            
            if slots:
                # Найдены слоты! Пытаемся забронировать
                best_slot = slots[0]  # Берем первый доступный слот
                slot_date = best_slot.get("date")
                
                logger.info(f"🎯 Найден слот для бронирования: {slot_date}")
                
                # Пытаемся забронировать через API
                booking_success = await api_client.create_supply_booking(
                    supply_id=supply_id,
                    warehouse_id=int(warehouse_id),
                    date=slot_date
                )
                
                if booking_success:
                    # Успешное бронирование!
                    await bot.send_message(
                        user_id,
                        f"🎉 <b>ПОСТАВКА ЗАБРОНИРОВАНА!</b>\n\n"
                        f"📦 Поставка: {supply_id}\n"
                        f"🏬 Склад: {warehouse_id}\n"
                        f"📅 Дата: {slot_date}\n"
                        f"⚡ Коэффициент: {best_slot.get('coefficient', 0)}x\n\n"
                        f"✅ Бронирование успешно создано!",
                        parse_mode="HTML"
                    )
                    break
                else:
                    logger.warning(f"⚠️ Не удалось забронировать слот {slot_date}")
            
            # Ждем 30 секунд перед следующей проверкой
            await asyncio.sleep(30)
            
    except Exception as e:
        logger.error(f"❌ Ошибка в автобронировании для пользователя {user_id}: {e}")
        await bot.send_message(
            user_id,
            f"❌ <b>Ошибка автобронирования</b>\n\n"
            f"Произошла ошибка в процессе автобронирования:\n"
            f"<code>{str(e)}</code>\n\n"
            f"Автобронирование остановлено.",
            parse_mode="HTML"
        )
    finally:
        # Очищаем сессию
        if user_id in monitoring_sessions:
            del monitoring_sessions[user_id]
        await browser_manager.close_browser(user_id)
        
        logger.info(f"🔴 Автобронирование остановлено для пользователя {user_id}")


@router.callback_query(F.data.startswith("stop_auto_book:"))
async def stop_auto_booking(callback: CallbackQuery):
    """Останавливает автобронирование."""
    user_id = int(callback.data.split(":")[1])
    
    if user_id in monitoring_sessions:
        monitoring_sessions[user_id]["status"] = "stopped"
        del monitoring_sessions[user_id]
        await browser_manager.close_browser(user_id)
        
        await callback.message.edit_text(
            "⏹ <b>Автобронирование остановлено</b>\n\n"
            "Мониторинг слотов прекращен.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 К поставкам", callback_data="view_supplies")],
                [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
            ])
        )
    else:
        await callback.answer("❌ Активное автобронирование не найдено", show_alert=True)


@router.callback_query(F.data.startswith("monitor_slots:"))
async def start_slots_monitoring(callback: CallbackQuery, state: FSMContext):
    """Запускает мониторинг слотов с уведомлениями."""
    warehouse_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    booking_supply_id = data.get("booking_supply_id")
    selected_supply = data.get("selected_supply")
    selected_warehouse = data.get("selected_warehouse")
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    
    supply_name = selected_supply.get("name", f"Поставка #{booking_supply_id}")
    warehouse_name = selected_warehouse.get("name", f"Склад #{warehouse_id}")
    
    await callback.message.edit_text(
        f"👁‍🗨 <b>Мониторинг слотов запущен!</b>\n\n"
        f"📦 <b>Поставка:</b> {supply_name}\n"
        f"🏬 <b>Склад:</b> {warehouse_name}\n"
        f"📅 <b>Период:</b> {date_from} - {date_to}\n\n"
        f"🔄 Проверяю слоты каждые 60 секунд\n"
        f"📬 Уведомления о новых слотах приходят автоматически\n\n"
        f"<i>Для остановки используйте кнопку ниже</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Остановить мониторинг", callback_data=f"stop_monitoring:{user_id}")],
            [InlineKeyboardButton(text="📊 Статус мониторинга", callback_data=f"monitoring_status:{user_id}")],
            [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
        ])
    )
    
    # Сохраняем сессию мониторинга
    monitoring_sessions[user_id] = {
        "supply_id": booking_supply_id,
        "supply_name": supply_name,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "date_from": date_from,
        "date_to": date_to,
        "status": "active",
        "last_slots": [],
        "notifications_sent": 0
    }
    
    # Запускаем фоновую задачу мониторинга
    asyncio.create_task(monitoring_task(user_id, callback.bot))


@router.callback_query(F.data.startswith("monitor_supply:"))
async def monitor_supply_directly(callback: CallbackQuery, state: FSMContext):
    """Мониторинг доступных слотов для поставки."""
    supply_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Получаем данные поставки из состояния
    data = await state.get_data()
    selected_supply = data.get("selected_supply")
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    
    # Получаем API ключи пользователя из PostgreSQL
    from .callbacks import get_user_api_keys_list
    api_keys = await get_user_api_keys_list(user_id)
    if not api_keys:
        await callback.answer("❌ API ключ не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"🔍 <b>Мониторинг слотов</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"⏳ Ищу доступные слоты на всех складах...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем список складов и доступные слоты
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            warehouses = await api_client.get_warehouses()
            
            if warehouses:
                # Берем топ-30 складов для мониторинга (баланс скорости и полноты)
                top_warehouses = warehouses[:30]
                warehouse_ids = [w.get("id") for w in top_warehouses if w.get("id")]
                available_slots = await api_client.get_acceptance_coefficients(warehouse_ids)
            else:
                available_slots = []
        
        # Группируем слоты по складам
        slots_by_warehouse = {}
        for slot in available_slots:
            wh_id = slot.get("warehouseID")
            if wh_id not in slots_by_warehouse:
                slots_by_warehouse[wh_id] = []
            slots_by_warehouse[wh_id].append(slot)
        
        # Сохраняем данные для пагинации мониторинга поставки
        monitoring_sessions[user_id] = {
            'supply_id': supply_id,
            'supply_name': supply_name,
            'warehouses': warehouses,
            'available_slots': available_slots,
            'slots_by_warehouse': slots_by_warehouse
        }
        
        # Отображаем первую страницу мониторинга
        await show_supply_monitoring_page(callback.message, 0, supply_id, supply_name, warehouses, available_slots, slots_by_warehouse)
        
    except Exception as e:
        logger.error(f"❌ Ошибка мониторинга поставки {supply_id}: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка мониторинга</b>\n\n"
            f"📦 <b>{supply_name}</b>\n"
            f"Не удалось получить данные о слотах.\n\n"
            f"Ошибка: <code>{escape_html(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"monitor_supply:{supply_id}")],
                [InlineKeyboardButton(text="⬅️ К поставке", callback_data="back_to_supply")]
            ])
        )


async def show_supply_monitoring_page(message, page: int, supply_id: str, supply_name: str, warehouses, available_slots, slots_by_warehouse):
    """Отображает страницу мониторинга поставки с пагинацией."""
    # Фильтруем только склады с доступными слотами
    warehouses_with_slots = [w for w in warehouses if w.get('id') in slots_by_warehouse]
    
    MONITORING_PER_PAGE = 5
    total_pages = (len(warehouses_with_slots) + MONITORING_PER_PAGE - 1) // MONITORING_PER_PAGE
    start_idx = page * MONITORING_PER_PAGE
    end_idx = min(start_idx + MONITORING_PER_PAGE, len(warehouses_with_slots))
    
    if available_slots:
        text = f"🎯 <b>Мониторинг слотов</b>\n\n"
        text += f"📦 <b>{supply_name}</b>\n"
        text += f"✅ Найдено доступных слотов: {len(available_slots)}\n"
        text += f"📄 Страница {page + 1} из {total_pages} (складов со слотами: {len(warehouses_with_slots)})\n\n"
        
        # Показываем склады текущей страницы
        for i in range(start_idx, end_idx):
            warehouse = warehouses_with_slots[i]
            wh_id = warehouse.get('id')
            wh_name = warehouse.get('name', f'Склад #{wh_id}')
            
            slots = slots_by_warehouse.get(wh_id, [])
            text += f"🏬 <b>{wh_name}</b>\n"
            text += f"   🎯 Слотов: {len(slots)}\n"
            
            # Показываем ближайшие даты
            dates = [slot.get("date", "").split("T")[0] for slot in slots[:3]]
            if dates:
                text += f"   📅 Даты: {', '.join(dates)}\n"
            
            text += "\n"
        
        text += "💡 <i>Нажмите 'Забронировать' для выбора конкретного склада</i>"
    else:
        text = f"🔍 <b>Мониторинг слотов</b>\n\n"
        text += f"📦 <b>{supply_name}</b>\n"
        text += f"⚠️ Доступных слотов не найдено\n\n"
        text += f"На ближайшие 14 дней нет свободных слотов.\n"
        text += f"Попробуйте позже или включите автоматический мониторинг."
    
    # Создаем клавиатуру с пагинацией
    keyboard = []
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"monitor_page:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"monitor_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Основные кнопки
    keyboard.extend([
        [InlineKeyboardButton(text="🎯 Забронировать слот", callback_data=f"book_supply:{supply_id}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"monitor_supply:{supply_id}")],
        [InlineKeyboardButton(text="⬅️ К поставке", callback_data="back_to_supply")]
    ])
    
    await message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("monitor_page:"))
async def show_monitor_page_handler(callback: CallbackQuery):
    """Обработчик пагинации мониторинга поставки."""
    await callback.answer()  # Отвечаем на callback сразу
    
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем сохраненные данные
    if user_id in monitoring_sessions:
        data = monitoring_sessions[user_id]
        supply_id = data['supply_id']
        supply_name = data['supply_name']
        warehouses = data['warehouses']
        available_slots = data['available_slots']
        slots_by_warehouse = data['slots_by_warehouse']
        
        await show_supply_monitoring_page(callback.message, page, supply_id, supply_name, warehouses, available_slots, slots_by_warehouse)
    else:
        await callback.answer("❌ Данные устарели, выполните мониторинг заново", show_alert=True)


@router.callback_query(F.data == "browser_login")
async def browser_login_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик входа в WB через браузер."""
    await callback.answer()
    
    await callback.message.edit_text(
        f"🔐 <b>Вход в Wildberries</b>\n\n"
        f"Для входа в аккаунт WB используйте браузерное бронирование:\n\n"
        f"1. Перейдите в 'Браузерное бронирование'\n"
        f"2. Введите номер телефона\n"
        f"3. Подтвердите SMS-кодом\n"
        f"4. После входа сессия сохранится\n\n"
        f"💡 В следующий раз авторизация не потребуется!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Браузерное бронирование", callback_data="browser_booking")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
        ])
    )


async def monitoring_task(user_id: int, bot):
    """Фоновая задача мониторинга слотов."""
    session = monitoring_sessions.get(user_id)
    if not session:
        return
    
    supply_name = session["supply_name"]
    warehouse_name = session["warehouse_name"]
    warehouse_id = session["warehouse_id"]
    date_from = session["date_from"]
    date_to = session["date_to"]
    
    logger.info(f"👁‍🗨 Запущен мониторинг слотов для пользователя {user_id}")
    
    try:
        while session.get("status") == "active":
            # Получаем API ключ пользователя из PostgreSQL
            from .callbacks import get_user_api_keys_list
            api_keys = await get_user_api_keys_list(user_id)
            if not api_keys:
                break
            
            # Проверяем слоты через API
            async with WBSuppliesAPIClient(api_keys[0]) as api_client:
                current_slots = await api_client.get_available_slots(
                    warehouse_id=int(warehouse_id),
                    date_from=date_from,
                    date_to=date_to
                )
            
            # Сравниваем с предыдущими слотами
            last_slots = session.get("last_slots", [])
            new_slots = []
            
            # Находим новые слоты
            for slot in current_slots:
                slot_date = slot.get("date")
                slot_coefficient = slot.get("coefficient", 0)
                
                # Проверяем, был ли этот слот в прошлый раз
                was_present = any(
                    old_slot.get("date") == slot_date and 
                    old_slot.get("coefficient") == slot_coefficient
                    for old_slot in last_slots
                )
                
                if not was_present:
                    new_slots.append(slot)
            
            # Отправляем уведомления о новых слотах
            if new_slots:
                slots_text = ""
                for slot in new_slots[:3]:  # Максимум 3 слота в уведомлении
                    date = slot.get("date", "")
                    coefficient = slot.get("coefficient", 0)
                    slots_text += f"📅 {date} - коэффициент {coefficient}x\n"
                
                if len(new_slots) > 3:
                    slots_text += f"... и еще {len(new_slots) - 3} слотов"
                
                await bot.send_message(
                    user_id,
                    f"🔔 <b>НОВЫЕ СЛОТЫ НАЙДЕНЫ!</b>\n\n"
                    f"📦 <b>Поставка:</b> {supply_name}\n"
                    f"🏬 <b>Склад:</b> {warehouse_name}\n\n"
                    f"✨ <b>Новые слоты:</b>\n{slots_text}\n\n"
                    f"🎯 Всего доступно: {len(current_slots)} слотов",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🤖 Забронировать автоматически", callback_data=f"auto_book:{warehouse_id}")],
                        [InlineKeyboardButton(text="⏹ Остановить мониторинг", callback_data=f"stop_monitoring:{user_id}")]
                    ])
                )
                
                session["notifications_sent"] += 1
                logger.info(f"📬 Отправлено уведомление о {len(new_slots)} новых слотах пользователю {user_id}")
            
            # Проверяем, исчезли ли слоты
            disappeared_slots = []
            for old_slot in last_slots:
                old_date = old_slot.get("date")
                old_coefficient = old_slot.get("coefficient", 0)
                
                # Проверяем, есть ли этот слот сейчас
                still_present = any(
                    current_slot.get("date") == old_date and 
                    current_slot.get("coefficient") == old_coefficient
                    for current_slot in current_slots
                )
                
                if not still_present:
                    disappeared_slots.append(old_slot)
            
            # Уведомляем об исчезнувших слотах (только если было много слотов)
            if disappeared_slots and len(last_slots) > 3:
                await bot.send_message(
                    user_id,
                    f"⚠️ <b>Слоты исчезли</b>\n\n"
                    f"📦 {supply_name}\n"
                    f"🏬 {warehouse_name}\n\n"
                    f"❌ Исчезло слотов: {len(disappeared_slots)}\n"
                    f"📊 Осталось слотов: {len(current_slots)}",
                    parse_mode="HTML"
                )
            
            # Сохраняем текущие слоты для следующего сравнения
            session["last_slots"] = current_slots
            
            # Ждем 60 секунд перед следующей проверкой
            await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f"❌ Ошибка в мониторинге слотов для пользователя {user_id}: {e}")
        await bot.send_message(
            user_id,
            f"❌ <b>Ошибка мониторинга</b>\n\n"
            f"Произошла ошибка в процессе мониторинга слотов:\n"
            f"<code>{str(e)}</code>\n\n"
            f"Мониторинг остановлен.",
            parse_mode="HTML"
        )
    finally:
        # Очищаем сессию
        if user_id in monitoring_sessions:
            del monitoring_sessions[user_id]
        
        logger.info(f"🔴 Мониторинг слотов остановлен для пользователя {user_id}")


@router.callback_query(F.data.startswith("stop_monitoring:"))
async def stop_monitoring(callback: CallbackQuery):
    """Останавливает мониторинг слотов."""
    user_id = int(callback.data.split(":")[1])
    
    session = monitoring_sessions.get(user_id)
    if session:
        session["status"] = "stopped"
        del monitoring_sessions[user_id]
        
        await callback.message.edit_text(
            "⏹ <b>Мониторинг остановлен</b>\n\n"
            f"📊 Всего уведомлений отправлено: {session.get('notifications_sent', 0)}\n"
            f"Мониторинг слотов прекращен.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 К поставкам", callback_data="view_supplies")],
                [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
            ])
        )
    else:
        await callback.answer("❌ Активный мониторинг не найден", show_alert=True)


@router.callback_query(F.data.startswith("monitoring_status:"))
async def show_monitoring_status(callback: CallbackQuery):
    """Показывает статус мониторинга."""
    user_id = int(callback.data.split(":")[1])
    
    session = monitoring_sessions.get(user_id)
    if session:
        supply_name = session.get("supply_name", "Неизвестно")
        warehouse_name = session.get("warehouse_name", "Неизвестно")
        notifications_sent = session.get("notifications_sent", 0)
        last_slots_count = len(session.get("last_slots", []))
        
        await callback.message.edit_text(
            f"📊 <b>Статус мониторинга</b>\n\n"
            f"📦 <b>Поставка:</b> {supply_name}\n"
            f"🏬 <b>Склад:</b> {warehouse_name}\n"
            f"🔄 <b>Статус:</b> Активен\n"
            f"📬 <b>Уведомлений отправлено:</b> {notifications_sent}\n"
            f"📊 <b>Текущих слотов:</b> {last_slots_count}\n\n"
            f"⏰ Следующая проверка через ~60 секунд",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏹ Остановить мониторинг", callback_data=f"stop_monitoring:{user_id}")],
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"monitoring_status:{user_id}")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )
    else:
        await callback.answer("❌ Активный мониторинг не найден", show_alert=True)


@router.message(BookingStates.waiting_for_phone)
async def process_phone_for_booking(message: Message, state: FSMContext):
    """Обработка номера телефона для бронирования."""
    logger.info(f"🔍 BOOKING: Processing phone from user {message.from_user.id}: {message.text}")
    user_id = message.from_user.id
    phone = message.text.strip()
    
    if phone.startswith('/'):
        return
    
    if not phone.startswith("+") or len(phone) < 10:
        await message.answer(
            "❌ Неверный формат номера.\n"
            "Введите в международном формате: +79991234567 или +996500441234"
        )
        return
    
    browser = await browser_manager.get_browser(user_id)
    if not browser:
        await message.answer("❌ Сессия браузера потеряна. Начните заново.")
        await state.clear()
        return
    
    data = await state.get_data()
    supply_name = data.get("supply_name", "Поставка")
    
    loading_msg = await message.answer(
        f"⏳ Ввожу номер в форму WB для поставки {supply_name}..."
    )
    
    try:
        success = await browser.login_step1_phone(phone)
        
        if success:
            await loading_msg.edit_text(
                f"✅ <b>Номер введен в форму WB!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"📱 Номер: {phone[:4]}****{phone[-2:]}\n"
                f"📨 СМС код отправлен на ваш телефон\n\n"
                f"🔑 Введите полученный код:"
            )
            
            await state.update_data(phone=phone)
            await state.set_state(BookingStates.waiting_for_sms_code)
        else:
            await loading_msg.edit_text(
                f"❌ <b>Ошибка ввода номера</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"Не удалось ввести номер в форму WB.\n"
                f"Попробуйте еще раз или обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{data.get('supply_id')}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            await state.clear()
        
    except Exception as e:
        logger.error(f"Error during phone input for booking: {e}")
        await loading_msg.edit_text(
            f"❌ Ошибка при входе для поставки {supply_name}.\n"
            f"Попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{data.get('supply_id')}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
            ])
        )


@router.message(BookingStates.waiting_for_sms_code)
async def process_sms_code_for_booking(message: Message, state: FSMContext):
    """Обработка СМС кода для бронирования."""
    user_id = message.from_user.id
    code = message.text.strip()
    
    if code.startswith('/'):
        return
    
    browser = await browser_manager.get_browser(user_id)
    if not browser:
        await message.answer("❌ Сессия браузера потеряна.")
        await state.clear()
        return
    
    data = await state.get_data()
    supply_name = data.get("supply_name", "Поставка")
    supply_id = data.get("supply_id")
    preorder_id = data.get("preorder_id")
    
    if not code.isdigit() or len(code) < 4 or len(code) > 6:
        await message.answer(
            "❌ Неверный формат кода.\n"
            "Введите 4-6 цифр из СМС."
        )
        return
    
    loading_msg = await message.answer(
        f"🔐 Ввожу СМС код в форму WB для поставки {supply_name}...\n"
        f"⏳ Проверяю вход..."
    )
    
    try:
        result = await browser.login_step2_sms(code)
        
        if result == "email_required":
            await loading_msg.edit_text(
                f"📧 <b>Требуется подтверждение по email</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"WB требует дополнительное подтверждение через электронную почту.\n\n"
                f"📋 <b>Что делать:</b>\n"
                f"1️⃣ Проверьте свою электронную почту\n"
                f"2️⃣ Найдите письмо от Wildberries\n"
                f"3️⃣ Перейдите по ссылке в письме\n"
                f"4️⃣ После подтверждения попробуйте снова\n\n"
                f"⚠️ Без подтверждения email авторизация невозможна.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            await state.clear()
        elif result:
            await loading_msg.edit_text(
                f"✅ <b>Вход выполнен успешно!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"🎯 Переходим к бронированию поставки...",
                parse_mode="HTML"
            )
            
            try:
                await browser.navigate_to_supplies_page()
                await asyncio.sleep(2)
                
                booking_result = await browser.book_supply_by_id(preorder_id, min_hours_ahead=80)
                
                if booking_result and booking_result.get("success"):
                    await loading_msg.edit_text(
                        f"🎉 <b>Поставка успешно забронирована!</b>\n\n"
                        f"📦 <b>{supply_name}</b>\n"
                        f"🆔 ID: <code>{supply_id}</code>\n"
                        f"📋 Заказ: <code>{preorder_id}</code>\n"
                        f"📅 Дата: {booking_result.get('date', 'Не указана')}\n"
                        f"🏬 Склад: {booking_result.get('warehouse', 'Не указан')}\n\n"
                        f"✅ Бронирование завершено!",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📦 Мои поставки", callback_data="view_supplies")],
                            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
                        ])
                    )
                else:
                    error_msg = booking_result.get("error", "Неизвестная ошибка") if booking_result else "Ошибка бронирования"
                    await loading_msg.edit_text(
                        f"❌ <b>Ошибка бронирования</b>\n\n"
                        f"📦 <b>{supply_name}</b>\n"
                        f"💥 {error_msg}",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                        ])
                    )
                    
            except Exception as e:
                logger.error(f"Error during booking after login: {e}")
                await loading_msg.edit_text(
                    f"❌ <b>Ошибка бронирования</b>\n\n"
                    f"📦 <b>{supply_name}</b>\n"
                    f"💥 Произошла ошибка: <code>{escape_html(str(e))}</code>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                    ])
                )
            
            await state.clear()
        else:
            await loading_msg.edit_text(
                f"❌ <b>Ошибка входа</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"Неверный SMS код или ошибка авторизации.\n"
                f"Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            await state.clear()
        
    except Exception as e:
        logger.error(f"Error during SMS input for booking: {e}")
        await loading_msg.edit_text(
            f"❌ Ошибка при вводе SMS кода для поставки {supply_name}.\n"
            f"Попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
            ])
        )
