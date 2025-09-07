"""
Обработчики для бронирования поставок
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from typing import List, Dict, Any
import asyncio

from ...utils.logger import get_logger
from ...services.wb_supplies_api import WBSuppliesAPIClient
from ...services.browser_automation import WBBrowserAutomationPro
from .callbacks import user_api_keys
from ..keyboards.inline import back_to_main_menu_keyboard

logger = get_logger(__name__)
router = Router()

# Глобальное хранилище сессий браузера для бронирования
booking_browser_sessions = {}

# Глобальное хранилище мониторинга слотов
monitoring_sessions = {}


class BookingStates(StatesGroup):
    """Состояния для бронирования поставок."""
    selecting_warehouse = State()
    selecting_dates = State()
    confirming_booking = State()
    monitoring_slots = State()


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
    
    await callback.message.edit_text(
        f"🎯 <b>Бронирование поставки</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"🆔 ID: <code>{supply_id}</code>\n\n"
        f"📅 Выберите период для поиска слотов:",
        parse_mode="HTML",
        reply_markup=create_date_range_keyboard()
    )
    
    # Сохраняем ID поставки для бронирования
    await state.update_data(booking_supply_id=supply_id)
    await state.set_state(BookingStates.selecting_dates)


@router.callback_query(F.data.startswith("date_range:"))
async def process_date_range(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор диапазона дат."""
    _, date_from_str, date_to_str = callback.data.split(":")
    user_id = callback.from_user.id
    
    # Получаем API ключи пользователя
    api_keys = user_api_keys.get(user_id, [])
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
            f"<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="back_to_supply")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
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
    date_from = data.get("date_from", "2025-09-07")
    date_to = data.get("date_to", "2025-09-14")
    
    if not selected_supply:
        await callback.answer("❌ Поставка не найдена", show_alert=True)
        return
    
    supply_name = selected_supply.get("name", f"Поставка #{supply_id}")
    preorder_id = selected_supply.get("preorderID")
    
    await callback.message.edit_text(
        f"🤖 <b>Запускаю автоматическое бронирование...</b>\n\n"
        f"📦 <b>{supply_name}</b>\n"
        f"🆔 ID: <code>{supply_id}</code>\n"
        f"📋 Заказ: <code>{preorder_id}</code>\n"
        f"📅 Период: {date_from} - {date_to}\n\n"
        f"⏳ Открываю браузер и выполняю вход...",
        parse_mode="HTML"
    )
    
    try:
        # Создаем экземпляр браузерной автоматизации
        browser = WBBrowserAutomationPro(headless=False, debug_mode=True)
        
        # Запускаем браузер
        if not await browser.start_browser():
            await callback.message.edit_text(
                f"❌ <b>Ошибка запуска браузера</b>\n\n"
                f"Не удалось запустить браузер для автоматизации.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            return
        
        # Проверяем авторизацию
        await callback.message.edit_text(
            f"🤖 <b>Браузер запущен!</b>\n\n"
            f"📦 <b>{supply_name}</b>\n"
            f"🔍 Проверяю авторизацию...",
            parse_mode="HTML"
        )
        
        # Проверяем, авторизован ли пользователь
        is_logged_in = await browser.check_if_logged_in()
        
        if not is_logged_in:
            # Если не авторизован - требуем вход через браузерное бронирование
            await callback.message.edit_text(
                f"🔐 <b>Требуется авторизация</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"❌ Пользователь не авторизован в WB\n\n"
                f"💡 Сначала выполните вход через браузер:\n"
                f"1. Нажмите 'Войти в WB'\n"
                f"2. Введите номер телефона и SMS-код\n"
                f"3. После входа повторите бронирование",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔐 Войти в WB", callback_data="browser_login")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_supply")]
                ])
            )
            await browser.close_browser()
            return
        
        # Обновляем статус
        await callback.message.edit_text(
            f"✅ <b>Вход выполнен!</b>\n\n"
            f"📦 <b>{supply_name}</b>\n"
            f"⏳ Ищу поставку и бронирую слот...",
            parse_mode="HTML"
        )
        
        # Выполняем бронирование поставки
        booking_success = await browser.book_supply(
            supply_id=str(supply_id),
            preorder_id=str(preorder_id),
            date_from=date_from,
            date_to=date_to
        )
        
        # Закрываем браузер
        await browser.close_browser()
        
        if booking_success:
            await callback.message.edit_text(
                f"🎉 <b>ПОСТАВКА ЗАБРОНИРОВАНА!</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"🆔 ID: <code>{supply_id}</code>\n"
                f"📋 Заказ: <code>{preorder_id}</code>\n"
                f"📅 Период: {date_from} - {date_to}\n\n"
                f"✅ Слот успешно забронирован через браузер!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 К поставкам", callback_data="view_supplies")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
        else:
            await callback.message.edit_text(
                f"⚠️ <b>Бронирование не удалось</b>\n\n"
                f"📦 <b>{supply_name}</b>\n"
                f"❌ Доступных слотов нет или произошла ошибка.\n\n"
                f"Попробуйте позже или выберите другие даты.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"browser_book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="📅 Другие даты", callback_data=f"book_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
                ])
            )
        
    except Exception as e:
        logger.error(f"❌ Ошибка автоматического бронирования: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка бронирования</b>\n\n"
            f"📦 <b>{supply_name}</b>\n"
            f"💥 Произошла ошибка: <code>{str(e)}</code>",
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
        # Создаем браузерную сессию для автобронирования
        browser = WBBrowserAutomationPro(headless=True, debug_mode=False)
        success = await browser.start_browser(headless=True)
        
        if not success:
            raise Exception("Не удалось запустить браузер")
        
        # Сохраняем браузерную сессию
        booking_browser_sessions[user_id] = {
            "browser": browser,
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
            f"<code>{str(e)}</code>",
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
        # Получаем API ключ пользователя
        api_keys = user_api_keys.get(user_id, [])
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
            f"<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"check_slots:{warehouse_id}")],
                [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="view_supplies")]
            ])
        )


async def auto_booking_task(user_id: int, bot):
    """Фоновая задача автобронирования."""
    session = booking_browser_sessions.get(user_id)
    if not session:
        return
    
    browser = session["browser"]
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
        if user_id in booking_browser_sessions:
            try:
                await booking_browser_sessions[user_id]["browser"].close_browser()
            except:
                pass
            del booking_browser_sessions[user_id]
        
        logger.info(f"🔴 Автобронирование остановлено для пользователя {user_id}")


@router.callback_query(F.data.startswith("stop_auto_book:"))
async def stop_auto_booking(callback: CallbackQuery):
    """Останавливает автобронирование."""
    user_id = int(callback.data.split(":")[1])
    
    session = booking_browser_sessions.get(user_id)
    if session:
        session["status"] = "stopped"
        try:
            await session["browser"].close_browser()
        except:
            pass
        del booking_browser_sessions[user_id]
        
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
    
    # Получаем API ключи пользователя
    api_keys = user_api_keys.get(user_id, [])
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
            f"Ошибка: <code>{str(e)}</code>",
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
            # Получаем API ключ пользователя  
            api_keys = user_api_keys.get(user_id, [])
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
