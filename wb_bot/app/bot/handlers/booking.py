"""
Обработчики для автоматического бронирования поставок.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from ..keyboards.inline import MainMenuCallback
from ..states import BookingStates
from ...services.wb_booking import booking_service
from ...services.wb_real_api import wb_real_api, user_api_keys
from .callbacks import user_api_keys as local_api_keys
from ...utils.logger import get_logger

logger = get_logger(__name__)

router = Router()

# Временное хранилище задач автобронирования
user_booking_tasks = {}  # user_id: {task_id: task_info}


@router.callback_query(F.data == "auto_booking")
async def show_booking_menu(callback: CallbackQuery):
    """Показать меню автобронирования."""
    user_id = callback.from_user.id
    
    # Проверяем наличие API ключей
    if not local_api_keys.get(user_id):
        await callback.answer("❌ Сначала добавьте API ключ", show_alert=True)
        return
    
    # Получаем активные задачи
    active_tasks = user_booking_tasks.get(user_id, {})
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ Создать автобронирование",
            callback_data="create_booking"
        )],
        [InlineKeyboardButton(
            text="📦 Забронировать поставку",
            callback_data="book_existing_supply"
        )],
        [InlineKeyboardButton(
            text="🌐 Браузерное бронирование",
            callback_data="browser_booking"
        )],
        [InlineKeyboardButton(
            text=f"📋 Активные задачи ({len(active_tasks)})",
            callback_data="list_bookings"
        )] if active_tasks else [],
        [InlineKeyboardButton(
            text="❓ Как это работает",
            callback_data="booking_help"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_main"
        )]
    ])
    
    text = (
        "🤖 <b>Автоматическое бронирование</b>\n\n"
        "Бот будет автоматически проверять наличие слотов "
        "и бронировать их по вашим критериям.\n\n"
        "⚡ <b>Преимущества:</b>\n"
        "• Мгновенное бронирование при появлении\n"
        "• Работает 24/7 без вашего участия\n"
        "• Выбор конкретных дат и складов\n"
        "• Фильтр по коэффициентам"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "booking_help")
async def show_booking_help(callback: CallbackQuery):
    """Показать справку по автобронированию."""
    text = (
        "❓ <b>Как работает автобронирование</b>\n\n"
        "1️⃣ <b>Создайте задачу:</b>\n"
        "• Выберите склад\n"
        "• Укажите даты для бронирования\n"
        "• Установите макс. коэффициент\n"
        "• Выберите частоту проверки\n\n"
        "2️⃣ <b>Бот начнет мониторинг:</b>\n"
        "• Проверяет слоты каждые N секунд\n"
        "• Ищет слоты с нужным коэффициентом\n"
        "• Автоматически бронирует при появлении\n\n"
        "3️⃣ <b>Вы получите уведомление:</b>\n"
        "• О успешном бронировании\n"
        "• С деталями поставки\n"
        "• Задача автоматически остановится\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Бронируется первый подходящий слот\n"
        "• Приоритет - слоты с x0\n"
        "• Одна задача = одно бронирование"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="auto_booking"
        )]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "create_booking")
async def create_booking_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание автобронирования."""
    user_id = callback.from_user.id
    
    # Синхронизируем API ключи
    user_api_keys.update(local_api_keys)
    
    # Получаем список складов
    loading_msg = await callback.message.edit_text(
        "⏳ Загружаю список складов...",
        parse_mode="HTML"
    )
    
    try:
        async with wb_real_api as service:
            warehouses = await service.get_warehouses(local_api_keys[user_id][0])
        
        if not warehouses:
            await loading_msg.edit_text(
                "❌ Не удалось получить список складов. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
                ])
            )
            return
        
        # Сохраняем склады в состояние
        await state.update_data(warehouses=warehouses)
        await state.set_state(BookingStates.selecting_warehouse)
        
        # Показываем основные склады
        main_warehouses = {
            117986: "Коледино",
            507: "Подольск",
            120762: "Электросталь",
            117501: "Казань",
            1733: "Екатеринбург",
            301: "СПб Шушары",
            206236: "Новосибирск",
            206348: "Хабаровск",
            130744: "Краснодар",
            208941: "СПб Уткина Заводь"
        }
        
        buttons = []
        for wh_id, wh_name in main_warehouses.items():
            # Проверяем есть ли склад в полученном списке
            if any(w.get("ID") == wh_id for w in warehouses):
                buttons.append([InlineKeyboardButton(
                    text=f"📦 {wh_name}",
                    callback_data=f"book_wh:{wh_id}:{wh_name}"
                )])
        
        buttons.append([InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="auto_booking"
        )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await loading_msg.edit_text(
            "📦 <b>Выберите склад для автобронирования:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        print(f"Error loading warehouses: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при загрузке складов. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
            ])
        )


@router.callback_query(F.data.startswith("book_wh:"))
async def select_warehouse_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбрать склад для автобронирования."""
    parts = callback.data.split(":")
    warehouse_id = int(parts[1])
    warehouse_name = parts[2]
    
    await state.update_data(
        warehouse_id=warehouse_id,
        warehouse_name=warehouse_name
    )
    
    # Показываем доступные даты
    loading_msg = await callback.message.edit_text(
        "⏳ Проверяю доступные даты...",
        parse_mode="HTML"
    )
    
    user_id = callback.from_user.id
    
    try:
        async with wb_real_api as service:
            # Получаем слоты на 30 дней
            slots = await service.find_available_slots(
                user_id=user_id,
                warehouse_id=warehouse_id,
                supply_type="boxes",
                max_coefficient=5,
                days_ahead=30
            )
        
        if not slots:
            await loading_msg.edit_text(
                f"❌ Нет доступных дат для склада {warehouse_name}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="create_booking")]
                ])
            )
            return
        
        # Группируем по датам
        dates_info = {}
        for slot in slots:
            date = slot['date']
            if date not in dates_info:
                dates_info[date] = {
                    'min_coef': slot['coefficient'],
                    'count': 1
                }
            else:
                dates_info[date]['min_coef'] = min(dates_info[date]['min_coef'], slot['coefficient'])
                dates_info[date]['count'] += 1
        
        # Сортируем даты
        sorted_dates = sorted(dates_info.keys())[:14]  # Показываем макс 14 дней
        
        await state.update_data(available_dates=sorted_dates)
        await state.set_state(BookingStates.selecting_dates)
        
        buttons = []
        for date in sorted_dates:
            info = dates_info[date]
            # Форматируем дату
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                date_str = date_obj.strftime("%d.%m")
                weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date_obj.weekday()]
            except:
                date_str = date
                weekday = ""
            
            button_text = f"📅 {date_str} {weekday} (x{info['min_coef']})"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"book_date:{date}"
            )])
        
        buttons.extend([
            [InlineKeyboardButton(
                text="✅ Выбрать все даты",
                callback_data="book_date:all"
            )],
            [InlineKeyboardButton(
                text="➡️ Продолжить",
                callback_data="book_dates_done"
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="auto_booking"
            )]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await loading_msg.edit_text(
            f"📅 <b>Выберите даты для автобронирования</b>\n\n"
            f"Склад: {warehouse_name}\n\n"
            f"💡 Можно выбрать несколько дат.\n"
            f"Бот забронирует первую доступную.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        print(f"Error loading dates: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при загрузке дат. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="create_booking")]
            ])
        )


@router.callback_query(F.data.startswith("book_date:"))
async def toggle_booking_date(callback: CallbackQuery, state: FSMContext):
    """Выбрать/отменить дату для бронирования."""
    data = await state.get_data()
    selected_dates = data.get('selected_dates', [])
    available_dates = data.get('available_dates', [])
    
    date = callback.data.split(":")[1]
    
    if date == "all":
        # Выбрать все даты
        selected_dates = available_dates.copy()
    else:
        # Toggle конкретной даты
        if date in selected_dates:
            selected_dates.remove(date)
        else:
            selected_dates.append(date)
    
    await state.update_data(selected_dates=selected_dates)
    
    # Обновляем клавиатуру
    warehouse_name = data.get('warehouse_name', '')
    
    buttons = []
    for avail_date in available_dates:
        try:
            date_obj = datetime.strptime(avail_date, "%Y-%m-%d")
            date_str = date_obj.strftime("%d.%m")
            weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date_obj.weekday()]
        except:
            date_str = avail_date
            weekday = ""
        
        is_selected = avail_date in selected_dates
        prefix = "✅" if is_selected else "📅"
        
        button_text = f"{prefix} {date_str} {weekday}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"book_date:{avail_date}"
        )])
    
    buttons.extend([
        [InlineKeyboardButton(
            text="✅ Выбрать все даты",
            callback_data="book_date:all"
        )],
        [InlineKeyboardButton(
            text="➡️ Продолжить" if selected_dates else "❌ Выберите даты",
            callback_data="book_dates_done" if selected_dates else "none"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="auto_booking"
        )]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    selected_info = f"\n\n✅ Выбрано дат: {len(selected_dates)}" if selected_dates else ""
    
    await callback.message.edit_text(
        f"📅 <b>Выберите даты для автобронирования</b>\n\n"
        f"Склад: {warehouse_name}{selected_info}\n\n"
        f"💡 Можно выбрать несколько дат.\n"
        f"Бот забронирует первую доступную.",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "book_dates_done")
async def finish_date_selection(callback: CallbackQuery, state: FSMContext):
    """Завершить выбор дат."""
    data = await state.get_data()
    selected_dates = data.get('selected_dates', [])
    
    if not selected_dates:
        await callback.answer("❌ Выберите хотя бы одну дату", show_alert=True)
        return
    
    await state.set_state(BookingStates.selecting_coefficient)
    
    # Показываем выбор коэффициента
    buttons = [
        [InlineKeyboardButton(text="✅ Только x0 (бесплатно)", callback_data="book_coef:0")],
        [InlineKeyboardButton(text="💰 До x1", callback_data="book_coef:1")],
        [InlineKeyboardButton(text="💰 До x2", callback_data="book_coef:2")],
        [InlineKeyboardButton(text="💰 До x3", callback_data="book_coef:3")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="auto_booking")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Форматируем выбранные даты
    dates_str = ", ".join([
        datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m")
        for d in sorted(selected_dates)[:5]
    ])
    if len(selected_dates) > 5:
        dates_str += f" и еще {len(selected_dates) - 5}"
    
    await callback.message.edit_text(
        f"💰 <b>Выберите максимальный коэффициент</b>\n\n"
        f"Склад: {data['warehouse_name']}\n"
        f"Даты: {dates_str}\n\n"
        f"🎯 Бот будет искать слоты с коэффициентом\n"
        f"не выше указанного",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("book_coef:"))
async def select_coefficient(callback: CallbackQuery, state: FSMContext):
    """Выбрать коэффициент."""
    coef = int(callback.data.split(":")[1])
    
    await state.update_data(max_coefficient=coef)
    await state.set_state(BookingStates.selecting_interval)
    
    # Показываем выбор интервала проверки
    buttons = [
        [InlineKeyboardButton(text="⚡ Каждую секунду (VIP)", callback_data="book_interval:1")],
        [InlineKeyboardButton(text="🚀 Каждые 5 секунд", callback_data="book_interval:5")],
        [InlineKeyboardButton(text="⏱ Каждые 10 секунд", callback_data="book_interval:10")],
        [InlineKeyboardButton(text="⏰ Каждые 30 секунд", callback_data="book_interval:30")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="auto_booking")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        f"⏱ <b>Выберите частоту проверки</b>\n\n"
        f"Чем чаще проверка, тем выше шанс\n"
        f"забронировать слот при появлении.\n\n"
        f"⚠️ <b>Внимание:</b> Частая проверка\n"
        f"создает нагрузку на API",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("book_interval:"))
async def start_auto_booking(callback: CallbackQuery, state: FSMContext):
    """Запустить автобронирование."""
    interval = int(callback.data.split(":")[1])
    
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # Создаем задачу
    task_id = str(uuid.uuid4())[:8]
    task_info = {
        'id': task_id,
        'warehouse_id': data['warehouse_id'],
        'warehouse_name': data['warehouse_name'],
        'selected_dates': data['selected_dates'],
        'max_coefficient': data['max_coefficient'],
        'check_interval': interval,
        'created_at': datetime.now().isoformat(),
        'status': 'active'
    }
    
    # Сохраняем задачу
    if user_id not in user_booking_tasks:
        user_booking_tasks[user_id] = {}
    user_booking_tasks[user_id][task_id] = task_info
    
    # Запускаем асинхронную задачу
    task = asyncio.create_task(
        booking_service.start_auto_booking(
            user_id=user_id,
            task_id=task_id,
            warehouse_id=data['warehouse_id'],
            warehouse_name=data['warehouse_name'],
            supply_type="boxes",  # TODO: добавить выбор типа
            target_dates=data['selected_dates'],
            max_coefficient=data['max_coefficient'],
            check_interval=interval
        )
    )
    
    # Сохраняем задачу в сервисе
    if user_id not in booking_service.active_bookings:
        booking_service.active_bookings[user_id] = {}
    booking_service.active_bookings[user_id][task_id] = task
    
    await state.clear()
    
    # Форматируем даты
    dates_str = ", ".join([
        datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m")
        for d in sorted(data['selected_dates'])[:3]
    ])
    if len(data['selected_dates']) > 3:
        dates_str += f" и еще {len(data['selected_dates']) - 3}"
    
    text = (
        f"✅ <b>Автобронирование запущено!</b>\n\n"
        f"🆔 ID задачи: {task_id}\n"
        f"📦 Склад: {data['warehouse_name']}\n"
        f"📅 Даты: {dates_str}\n"
        f"💰 Макс. коэффициент: x{data['max_coefficient']}\n"
        f"⏱ Проверка: каждые {interval} сек\n\n"
        f"🔔 Вы получите уведомление при успешном бронировании.\n\n"
        f"💡 Задача остановится автоматически после бронирования."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="list_bookings")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="auto_booking")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer("✅ Автобронирование запущено!", show_alert=True)


@router.callback_query(F.data == "list_bookings")
async def list_booking_tasks(callback: CallbackQuery):
    """Показать список задач автобронирования."""
    user_id = callback.from_user.id
    tasks = user_booking_tasks.get(user_id, {})
    
    if not tasks:
        await callback.message.edit_text(
            "📋 <b>У вас нет активных задач автобронирования</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать", callback_data="create_booking")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
            ])
        )
        return
    
    text = "📋 <b>Ваши задачи автобронирования:</b>\n\n"
    
    buttons = []
    for task_id, task in tasks.items():
        # Форматируем информацию
        created = datetime.fromisoformat(task['created_at'])
        duration = datetime.now() - created
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        text += (
            f"🔸 <b>ID: {task_id}</b>\n"
            f"📦 {task['warehouse_name']}\n"
            f"📅 Дат: {len(task['selected_dates'])}\n"
            f"💰 До x{task['max_coefficient']}\n"
            f"⏱ Каждые {task['check_interval']} сек\n"
            f"⏳ Работает: {hours}ч {minutes}мин\n\n"
        )
        
        buttons.append([InlineKeyboardButton(
            text=f"❌ Остановить {task_id}",
            callback_data=f"stop_booking:{task_id}"
        )])
    
    buttons.extend([
        [InlineKeyboardButton(text="➕ Создать еще", callback_data="create_booking")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stop_booking:"))
async def stop_booking_task(callback: CallbackQuery):
    """Остановить задачу автобронирования."""
    task_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Останавливаем задачу
    booking_service.stop_booking(user_id, task_id)
    
    # Удаляем из локального хранилища
    if user_id in user_booking_tasks and task_id in user_booking_tasks[user_id]:
        del user_booking_tasks[user_id][task_id]
    
    await callback.answer("✅ Задача остановлена", show_alert=True)
    
    # Обновляем список
    await list_booking_tasks(callback)


@router.callback_query(F.data == "book_existing_supply")
async def show_existing_supplies(callback: CallbackQuery):
    """Показать список существующих поставок для бронирования."""
    user_id = callback.from_user.id
    
    # Проверяем наличие API ключей
    if not local_api_keys.get(user_id):
        await callback.answer("❌ Сначала добавьте API ключ", show_alert=True)
        return
    
    # Синхронизируем API ключи
    user_api_keys.update(local_api_keys)
    
    loading_msg = await callback.message.edit_text(
        "⏳ Загружаю список ваших поставок...",
        parse_mode="HTML"
    )
    
    try:
        # Используем новый сервис для получения поставок
        from app.services.wb_supplies_new import WBSuppliesService
        
        async with WBSuppliesService() as wb_service:
            supplies = await wb_service.get_available_supplies_for_booking(local_api_keys[user_id][0])
        
        if not supplies:
            await loading_msg.edit_text(
                "📦 <b>Поставки не найдены</b>\n\n"
                "Не удалось получить список поставок.\n"
                "Возможные причины:\n"
                "• Неверный API ключ\n"
                "• Нет созданных поставок\n"
                "• Проблемы с API WB\n\n"
                "Проверьте логи бота для деталей.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
                ])
            )
            return
        
        # Показываем список поставок
        buttons = []
        text = f"📦 <b>Ваши незапланированные поставки ({len(supplies)} шт):</b>\n\n"
        
        if len(supplies) == 0:
            text += "У вас нет поставок со статусом 'Не запланировано'.\n\n"
            text += "💡 Создайте новую поставку в личном кабинете WB\n"
            text += "и она появится здесь для бронирования."
        
        # Ограничиваем текст, чтобы не превысить лимит Telegram (4096 символов)
        max_supplies_to_show = 50  # Максимум поставок для отображения
        
        for i, supply in enumerate(supplies[:max_supplies_to_show]):  # Показываем до 50 поставок
            supply_id = supply.get("supplyID")
            preorder_id = supply.get("preorderID")
            status = supply.get("statusName", "Не запланировано")
            phone = supply.get("phone", "")
            
            # Форматируем дату создания
            create_date = supply.get("createDate", "")
            if create_date:
                try:
                    from datetime import datetime
                    date_obj = datetime.fromisoformat(create_date.replace('Z', '+00:00').replace('+03:00', '+00:00'))
                    date_str = date_obj.strftime("%d.%m.%Y")
                except:
                    date_str = create_date[:10] if len(create_date) >= 10 else create_date
            else:
                date_str = "Неизвестна"
            
            text += (
                f"🔴 <b>Поставка #{supply_id or preorder_id or f'ID{i+1}'}</b>\n"
                f"📅 Создана: {date_str}\n"
                f"📋 Статус: {status}\n"
                f"📞 Телефон: {phone}\n\n"
            )
            
            # Добавляем кнопку для бронирования
            buttons.append([InlineKeyboardButton(
                text=f"📦 Забронировать #{supply_id or preorder_id or f'ID{i+1}'}",
                callback_data=f"select_supply:{supply_id or preorder_id}"
            )])
        
        # Если поставок больше чем показано
        if len(supplies) > max_supplies_to_show:
            text += f"\n<i>... и еще {len(supplies) - max_supplies_to_show} поставок</i>\n"
            text += f"<i>Показаны первые {max_supplies_to_show} поставок</i>\n"
        
        buttons.append([InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="auto_booking"
        )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await loading_msg.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        print(f"Error loading supplies: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при загрузке поставок. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
            ])
        )


@router.callback_query(F.data.startswith("select_supply:"))
async def select_supply_for_booking(callback: CallbackQuery, state: FSMContext):
    """Выбрать поставку для бронирования."""
    supply_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Сохраняем ID поставки
    await state.update_data(selected_supply_id=supply_id)
    await state.set_state(BookingStates.selecting_supply)
    
    # Показываем меню выбора режима бронирования
    text = (
        f"🎯 <b>Выберите режим бронирования для поставки #{supply_id}:</b>\n\n"
        f"📅 <b>Ручной выбор</b> - выберите конкретную дату из доступных\n"
        f"🤖 <b>Автопоиск в периоде</b> - укажите диапазон дат, бот будет искать и бронировать первый доступный слот\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ручной выбор даты", callback_data=f"manual_booking:{supply_id}")],
        [InlineKeyboardButton(text="🤖 Автопоиск в периоде", callback_data=f"auto_period:{supply_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("manual_booking:"))
async def manual_booking_handler(callback: CallbackQuery, state: FSMContext):
    """Ручной выбор даты для бронирования."""
    supply_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    loading_msg = await callback.message.edit_text(
        "⏳ Загружаю доступные даты...",
        parse_mode="HTML"
    )
    
    try:
        async with wb_real_api as service:
            supply_details = await service.get_supply_details(local_api_keys[user_id][0], supply_id)
            
            if not supply_details:
                await loading_msg.edit_text(
                    "❌ Не удалось загрузить детали поставки",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_supply:{supply_id}")]
                    ])
                )
                return
            
            # Получаем доступные слоты для бронирования
            warehouse_id = supply_details.get("warehouseID") or supply_details.get("actualWarehouseID")
            if not warehouse_id:
                await loading_msg.edit_text(
                    "❌ Не удалось определить склад для поставки",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
                    ])
                )
                return
            
            # Сохраняем данные поставки
            await state.update_data(
                supply_details=supply_details,
                warehouse_id=warehouse_id
            )
            
            # Получаем доступные слоты
            slots = await service.find_available_slots(
                user_id=user_id,
                warehouse_id=warehouse_id,
                supply_type="boxes",
                max_coefficient=3,
                days_ahead=14
            )
            
            if not slots:
                await loading_msg.edit_text(
                    f"❌ <b>Нет доступных слотов</b>\n\n"
                    f"🆔 Поставка: #{supply_id}\n"
                    f"📦 Склад: {supply_details.get('warehouseName', 'Неизвестен')}\n\n"
                    f"Попробуйте позже или выберите другую поставку.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
                    ])
                )
                return
            
            # Показываем доступные даты для бронирования
            dates_info = {}
            for slot in slots:
                date = slot['date']
                if date not in dates_info:
                    dates_info[date] = {
                        'min_coef': slot['coefficient'],
                        'count': 1
                    }
                else:
                    dates_info[date]['min_coef'] = min(dates_info[date]['min_coef'], slot['coefficient'])
                    dates_info[date]['count'] += 1
            
            # Сортируем даты
            sorted_dates = sorted(dates_info.keys())[:10]  # Показываем макс 10 дат
            
            buttons = []
            for date in sorted_dates:
                info = dates_info[date]
                # Форматируем дату
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    date_str = date_obj.strftime("%d.%m")
                    weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date_obj.weekday()]
                except:
                    date_str = date
                    weekday = ""
                
                button_text = f"📅 {date_str} {weekday} (x{info['min_coef']})"
                buttons.append([InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"book_supply_date:{date}"
                )])
            
            buttons.append([InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="book_existing_supply"
            )])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            text = (
                f"📅 <b>Выберите дату для бронирования</b>\n\n"
                f"🆔 Поставка: #{supply_id}\n"
                f"📦 Склад: {supply_details.get('warehouseName', 'Неизвестен')}\n"
                f"📋 Статус: {supply_details.get('statusName', 'Неизвестен')}\n"
                f"📞 Телефон: {supply_details.get('phone', 'Не указан')}\n\n"
                f"💡 Выберите дату с подходящим коэффициентом:"
            )
            
            await loading_msg.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
    except Exception as e:
        print(f"Error loading supply details: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при загрузке данных. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
            ])
        )


@router.callback_query(F.data.startswith("auto_period:"))
async def auto_period_booking(callback: CallbackQuery, state: FSMContext):
    """Автопоиск слотов в выбранном периоде."""
    supply_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Сохраняем данные
    await state.update_data(
        supply_id=supply_id,
        booking_mode="auto_period"
    )
    await state.set_state(BookingStates.selecting_start_date)
    
    # Показываем простой календарь для выбора начальной даты
    from datetime import datetime, timedelta
    
    text = (
        f"📅 <b>Выберите период для автопоиска слотов</b>\n\n"
        f"🆔 Поставка: #{supply_id}\n\n"
        f"<b>Шаг 1/2:</b> Выберите начальную дату периода\n\n"
        f"💡 Бот будет искать доступные слоты в указанном периоде\n"
        f"и автоматически забронирует первый подходящий"
    )
    
    # Создаем простой календарь с датами на ближайшие 30 дней
    today = datetime.now().date()
    buttons = []
    
    for i in range(0, 30, 3):  # По 3 даты в строке
        row = []
        for j in range(3):
            day_offset = i + j
            if day_offset < 30:
                target_date = today + timedelta(days=day_offset)
                row.append(InlineKeyboardButton(
                    text=target_date.strftime("%d.%m"),
                    callback_data=f"start_date:{target_date.strftime('%Y-%m-%d')}"
                ))
        if row:
            buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="book_existing_supply")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("start_date:"), BookingStates.selecting_start_date)
async def handle_start_date_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора начальной даты периода."""
    from datetime import datetime, timedelta
    
    selected_date = callback.data.split(":")[1]  # Формат: YYYY-MM-DD
    await state.update_data(start_date=selected_date)
    await state.set_state(BookingStates.selecting_end_date)
    
    data = await state.get_data()
    supply_id = data.get('supply_id')
    
    text = (
        f"📅 <b>Выберите период для автопоиска слотов</b>\n\n"
        f"🆔 Поставка: #{supply_id}\n"
        f"📍 Начало периода: <b>{selected_date}</b>\n\n"
        f"<b>Шаг 2/2:</b> Выберите конечную дату периода"
    )
    
    # Создаем календарь с датами после выбранной начальной даты
    start = datetime.strptime(selected_date, "%Y-%m-%d").date()
    buttons = []
    
    for i in range(1, 31, 3):  # Начинаем с 1 дня после начальной даты
        row = []
        for j in range(3):
            day_offset = i + j
            if day_offset <= 30:
                target_date = start + timedelta(days=day_offset)
                row.append(InlineKeyboardButton(
                    text=target_date.strftime("%d.%m"),
                    callback_data=f"end_date:{target_date.strftime('%Y-%m-%d')}"
                ))
        if row:
            buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="book_existing_supply")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("end_date:"), BookingStates.selecting_end_date)
async def handle_end_date_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора конечной даты периода."""
    end_date = callback.data.split(":")[1]  # Формат: YYYY-MM-DD
    data = await state.get_data()
    start_date = data.get('start_date')
    supply_id = data.get('supply_id')
    
    await state.update_data(end_date=end_date)
    await state.set_state(BookingStates.confirming_dates)
    
    # Показываем подтверждение
    text = (
        f"✅ <b>Подтвердите параметры автопоиска</b>\n\n"
        f"🆔 Поставка: #{supply_id}\n"
        f"📅 Период: с {start_date} по {end_date}\n\n"
        f"🎯 <b>Параметры поиска:</b>\n"
        f"• Коэффициент: x1 - x3\n"
        f"• Тип поставки: Короба\n"
        f"• Интервал проверки: 1 сек\n\n"
        f"⚡ Бот начнет мониторинг и забронирует первый доступный слот"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать автопоиск", callback_data="start_auto_search")],
        [InlineKeyboardButton(text="⚙️ Настроить параметры", callback_data="configure_search")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="book_existing_supply")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "start_auto_search", BookingStates.confirming_dates)
async def start_auto_search(callback: CallbackQuery, state: FSMContext):
    """Запуск автопоиска слотов в периоде."""
    data = await state.get_data()
    supply_id = data.get('supply_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    user_id = callback.from_user.id
    
    await state.set_state(BookingStates.monitoring_slots)
    
    # Показываем статус мониторинга
    monitoring_msg = await callback.message.edit_text(
        f"🔍 <b>Запускаю автопоиск...</b>\n\n"
        f"🆔 Поставка: #{supply_id}\n"
        f"📅 Период: {start_date} - {end_date}\n\n"
        f"⏳ Поиск доступных слотов...",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Остановить поиск", callback_data="stop_auto_search")]
        ])
    )
    
    try:
        # Запускаем мониторинг в фоне
        import asyncio
        from datetime import datetime, timedelta
        
        async with wb_real_api as service:
            # Получаем детали поставки
            supply_details = await service.get_supply_details(local_api_keys[user_id][0], supply_id)
            
            if not supply_details:
                await monitoring_msg.edit_text(
                    "❌ Не удалось загрузить детали поставки",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
                    ])
                )
                return
            
            warehouse_id = supply_details.get("warehouseID") or supply_details.get("actualWarehouseID")
            
            # Цикл мониторинга
            attempts = 0
            max_attempts = 300  # 5 минут максимум
            
            while attempts < max_attempts:
                current_state = await state.get_state()
                if current_state != BookingStates.monitoring_slots:
                    # Поиск остановлен
                    break
                
                attempts += 1
                
                # Ищем слоты
                slots = await service.find_available_slots(
                    user_id=user_id,
                    warehouse_id=warehouse_id,
                    supply_type="boxes",
                    max_coefficient=3,
                    days_ahead=30
                )
                
                # Фильтруем по периоду
                filtered_slots = []
                for slot in slots:
                    slot_date = datetime.strptime(slot['date'], "%Y-%m-%d").date()
                    start = datetime.strptime(start_date, "%Y-%m-%d").date()
                    end = datetime.strptime(end_date, "%Y-%m-%d").date()
                    
                    if start <= slot_date <= end:
                        filtered_slots.append(slot)
                
                if filtered_slots:
                    # Нашли слот! Бронируем
                    best_slot = min(filtered_slots, key=lambda x: x['coefficient'])
                    
                    await monitoring_msg.edit_text(
                        f"✅ <b>Найден слот!</b>\n\n"
                        f"📅 Дата: {best_slot['date']}\n"
                        f"⏰ Время: {best_slot['time']}\n"
                        f"📊 Коэффициент: x{best_slot['coefficient']}\n\n"
                        f"⏳ Бронирую...",
                        parse_mode="HTML"
                    )
                    
                    # Бронируем
                    from app.services.wb_booking import WBBookingService
                    booking_service = WBBookingService()
                    
                    result = await booking_service.book_existing_supply(
                        api_key=local_api_keys[user_id][0],
                        supply_id=supply_id,
                        date=best_slot['date']
                    )
                    
                    if result.get('success'):
                        await monitoring_msg.edit_text(
                            f"🎉 <b>Поставка успешно забронирована!</b>\n\n"
                            f"🆔 Поставка: #{supply_id}\n"
                            f"📅 Дата: {best_slot['date']}\n"
                            f"⏰ Время: {best_slot['time']}\n"
                            f"📊 Коэффициент: x{best_slot['coefficient']}\n"
                            f"📦 Склад: {supply_details.get('warehouseName', 'Неизвестен')}\n\n"
                            f"✅ Поставка забронирована в личном кабинете WB",
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📋 Мои поставки", callback_data="book_existing_supply")],
                                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                            ])
                        )
                    else:
                        error_msg = result.get('error', 'Неизвестная ошибка')
                        await monitoring_msg.edit_text(
                            f"❌ <b>Не удалось забронировать</b>\n\n"
                            f"Причина: {error_msg}\n\n"
                            f"Попробуйте еще раз",
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="🔄 Повторить", callback_data=f"select_supply:{supply_id}")],
                                [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
                            ])
                        )
                    
                    await state.clear()
                    return
                
                # Обновляем статус
                if attempts % 10 == 0:  # Каждые 10 попыток
                    await monitoring_msg.edit_text(
                        f"🔍 <b>Автопоиск активен</b>\n\n"
                        f"🆔 Поставка: #{supply_id}\n"
                        f"📅 Период: {start_date} - {end_date}\n\n"
                        f"⏳ Проверено попыток: {attempts}\n"
                        f"📊 Слотов в периоде: {len(filtered_slots)}\n\n"
                        f"<i>Поиск продолжается...</i>",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⏹ Остановить поиск", callback_data="stop_auto_search")]
                        ])
                    )
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(1)
            
            # Поиск завершен без результата
            await monitoring_msg.edit_text(
                f"⏱ <b>Автопоиск завершен</b>\n\n"
                f"За {attempts} попыток не найдено доступных слотов в периоде {start_date} - {end_date}\n\n"
                f"Попробуйте изменить период или параметры поиска",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Изменить период", callback_data=f"auto_period:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ К поставкам", callback_data="book_existing_supply")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error in auto search: {e}")
        await monitoring_msg.edit_text(
            "❌ Ошибка при автопоиске. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
            ])
        )
    
    await state.clear()


@router.callback_query(F.data == "stop_auto_search")
async def stop_auto_search(callback: CallbackQuery, state: FSMContext):
    """Остановка автопоиска."""
    await state.clear()
    
    await callback.message.edit_text(
        "⏹ <b>Автопоиск остановлен</b>\n\n"
        "Вы можете запустить его снова в любое время",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои поставки", callback_data="book_existing_supply")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )


@router.callback_query(F.data.startswith("book_supply_date:"))
async def book_supply_on_date(callback: CallbackQuery, state: FSMContext):
    """Забронировать поставку на выбранную дату."""
    selected_date = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    data = await state.get_data()
    supply_id = data.get('selected_supply_id')
    warehouse_id = data.get('warehouse_id')
    supply_details = data.get('supply_details', {})
    
    if not supply_id or not warehouse_id:
        await callback.answer("❌ Ошибка: данные поставки потеряны", show_alert=True)
        return
    
    # Показываем процесс бронирования
    booking_msg = await callback.message.edit_text(
        f"⏳ <b>Бронирую поставку...</b>\n\n"
        f"🆔 Поставка: #{supply_id}\n"
        f"📅 Дата: {selected_date}\n"
        f"📦 Склад: {supply_details.get('warehouseName', 'Неизвестен')}",
        parse_mode="HTML"
    )
    
    # Выполняем бронирование
    try:
        success, message = await booking_service.book_existing_supply(
            user_id=user_id,
            supply_id=supply_id,
            warehouse_id=warehouse_id,
            supply_date=selected_date
        )
        
        if success:
            # Успешно забронировано
            await booking_msg.edit_text(
                message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Другая поставка", callback_data="book_existing_supply")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_main")]
                ])
            )
            
            # Уведомляем об успехе
            await callback.answer("✅ Поставка успешно забронирована!", show_alert=True)
            
        else:
            # Ошибка бронирования
            await booking_msg.edit_text(
                message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать еще", callback_data=f"select_supply:{supply_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
                ])
            )
            
            await callback.answer("❌ Не удалось забронировать", show_alert=True)
    
    except Exception as e:
        print(f"Error booking supply: {e}")
        await booking_msg.edit_text(
            f"❌ <b>Ошибка бронирования</b>\n\n{str(e)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="book_existing_supply")]
            ])
        )
    
    # Очищаем состояние
    await state.clear()
