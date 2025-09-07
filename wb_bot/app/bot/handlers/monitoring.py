"""
Monitoring management handlers.

This module contains handlers for creating, managing, and configuring
monitoring tasks for warehouse slots.
"""

from datetime import date
from typing import Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

from ...database import get_session, User, MonitoringTask
from ...database.models import SupplyType, DeliveryType, MonitoringMode
from ...services.auth import auth_service
from ...utils.logger import UserLogger
from ..keyboards.inline import (
    MonitoringCallback, get_monitoring_menu, get_monitoring_list_keyboard,
    get_monitoring_task_keyboard, get_supply_type_keyboard, get_delivery_type_keyboard,
    get_monitoring_mode_keyboard, get_coefficient_keyboard, get_check_interval_keyboard,
    get_confirmation_keyboard, SettingsCallback
)
from ..keyboards.calendar import (
    get_date_range_calendar, handle_calendar_callback, CalendarCallback
)
from ..states import MonitoringStates

router = Router()


@router.callback_query(MonitoringCallback.filter(F.action == "create"))
async def start_create_monitoring(callback: CallbackQuery, state: FSMContext):
    """Start creating new monitoring task."""
    user_id = callback.from_user.id
    user_logger = UserLogger(user_id)
    
    # Check if user has API keys
    api_keys = await auth_service.get_user_api_keys(user_id)
    if not api_keys:
        await callback.answer(
            "❌ Сначала добавьте API ключ в разделе 'API ключи'",
            show_alert=True
        )
        return
    
    # Check if user can create monitoring (trial or premium)
    async with get_session() as session:
        query = select(User).where(User.id == user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user or not user.can_use_auto_booking():
            await callback.answer(
                "❌ Пробный период исчерпан. Необходима Premium подписка",
                show_alert=True
            )
            return
    
    # Initialize monitoring creation
    await state.set_data({
        'supply_type': user.default_supply_type,
        'delivery_type': user.default_delivery_type,
        'monitoring_mode': user.default_monitoring_mode,
        'max_coefficient': user.default_max_coefficient,
        'check_interval': user.default_check_interval
    })
    
    step_text = (
        "📊 <b>Создание мониторинга слотов</b>\n\n"
        "Шаг 1/6: Выберите склад\n\n"
        "Введите ID склада или название для поиска:"
    )
    
    await callback.message.edit_text(step_text, parse_mode="HTML")
    await state.set_state(MonitoringStates.waiting_for_warehouse_selection)
    await callback.answer()


@router.message(StateFilter(MonitoringStates.waiting_for_warehouse_selection))
async def handle_warehouse_selection(message: Message, state: FSMContext):
    """Handle warehouse selection."""
    warehouse_input = message.text.strip()
    
    # Try to parse as ID first
    try:
        warehouse_id = int(warehouse_input)
        warehouse_name = f"Склад {warehouse_id}"  # Default name
    except ValueError:
        # Search by name (simplified - in real implementation would search via API)
        warehouse_name = warehouse_input
        warehouse_id = 1  # Placeholder - would be resolved via API
    
    # Save warehouse info
    await state.update_data(
        warehouse_id=warehouse_id,
        warehouse_name=warehouse_name
    )
    
    # Move to date selection
    step_text = (
        f"📊 <b>Создание мониторинга слотов</b>\n\n"
        f"Шаг 2/6: Период мониторинга\n\n"
        f"📦 <b>Склад:</b> {warehouse_name}\n\n"
        "Выберите период для мониторинга:"
    )
    
    await message.answer(
        step_text,
        parse_mode="HTML",
        reply_markup=get_date_range_calendar(message.from_user.id)
    )
    await state.set_state(MonitoringStates.waiting_for_date_range)


@router.callback_query(
    CalendarCallback.filter(),
    StateFilter(MonitoringStates.waiting_for_date_range)
)
async def handle_date_selection(
    callback: CallbackQuery,
    callback_data: CalendarCallback,
    state: FSMContext
):
    """Handle date range selection."""
    user_id = callback.from_user.id
    
    result_text, new_keyboard, selected_dates = handle_calendar_callback(
        user_id, callback_data
    )
    
    if new_keyboard:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    
    if selected_dates:
        start_date, end_date = selected_dates
        await state.update_data(date_from=start_date, date_to=end_date)
        
        # Move to supply type selection
        data = await state.get_data()
        
        step_text = (
            f"📊 <b>Создание мониторинга слотов</b>\n\n"
            f"Шаг 3/6: Тип поставки\n\n"
            f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
            f"📅 <b>Период:</b> {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            "Выберите тип поставки:"
        )
        
        await callback.message.edit_text(
            step_text,
            parse_mode="HTML",
            reply_markup=get_supply_type_keyboard()
        )
        await state.set_state(MonitoringStates.waiting_for_supply_type)
    
    await callback.answer(result_text if not new_keyboard else "")


@router.callback_query(
    SettingsCallback.filter(F.action == "supply_type"),
    StateFilter(MonitoringStates.waiting_for_supply_type)
)
async def handle_supply_type_selection(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext
):
    """Handle supply type selection."""
    supply_type = callback_data.value
    await state.update_data(supply_type=supply_type)
    
    data = await state.get_data()
    
    supply_type_text = "📦 Короб" if supply_type == "box" else "🏗 Монопаллета"
    
    step_text = (
        f"📊 <b>Создание мониторинга слотов</b>\n\n"
        f"Шаг 4/6: Тип доставки\n\n"
        f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📅 <b>Период:</b> {data['date_from'].strftime('%d.%m.%Y')} - {data['date_to'].strftime('%d.%m.%Y')}\n"
        f"📦 <b>Тип поставки:</b> {supply_type_text}\n\n"
        "Выберите тип доставки:"
    )
    
    await callback.message.edit_text(
        step_text,
        parse_mode="HTML",
        reply_markup=get_delivery_type_keyboard()
    )
    await state.set_state(MonitoringStates.waiting_for_delivery_type)
    await callback.answer()


@router.callback_query(
    SettingsCallback.filter(F.action == "delivery_type"),
    StateFilter(MonitoringStates.waiting_for_delivery_type)
)
async def handle_delivery_type_selection(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext
):
    """Handle delivery type selection."""
    delivery_type = callback_data.value
    await state.update_data(delivery_type=delivery_type)
    
    data = await state.get_data()
    
    delivery_type_text = "🚚 Прямая" if delivery_type == "direct" else "🔄 Транзитная"
    supply_type_text = "📦 Короб" if data['supply_type'] == "box" else "🏗 Монопаллета"
    
    step_text = (
        f"📊 <b>Создание мониторинга слотов</b>\n\n"
        f"Шаг 5/6: Режим мониторинга\n\n"
        f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📅 <b>Период:</b> {data['date_from'].strftime('%d.%m.%Y')} - {data['date_to'].strftime('%d.%m.%Y')}\n"
        f"📦 <b>Тип поставки:</b> {supply_type_text}\n"
        f"🚚 <b>Тип доставки:</b> {delivery_type_text}\n\n"
        "Выберите режим мониторинга:"
    )
    
    await callback.message.edit_text(
        step_text,
        parse_mode="HTML",
        reply_markup=get_monitoring_mode_keyboard()
    )
    await state.set_state(MonitoringStates.waiting_for_monitoring_mode)
    await callback.answer()


@router.callback_query(
    SettingsCallback.filter(F.action == "mode"),
    StateFilter(MonitoringStates.waiting_for_monitoring_mode)
)
async def handle_monitoring_mode_selection(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext
):
    """Handle monitoring mode selection."""
    monitoring_mode = callback_data.value
    await state.update_data(monitoring_mode=monitoring_mode)
    
    data = await state.get_data()
    
    mode_text = "🔔 Только уведомления" if monitoring_mode == "notification" else "🤖 Автобронирование"
    delivery_type_text = "🚚 Прямая" if data['delivery_type'] == "direct" else "🔄 Транзитная"
    supply_type_text = "📦 Короб" if data['supply_type'] == "box" else "🏗 Монопаллета"
    
    step_text = (
        f"📊 <b>Создание мониторинга слотов</b>\n\n"
        f"Шаг 6/6: Настройки фильтрации\n\n"
        f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
        f"📅 <b>Период:</b> {data['date_from'].strftime('%d.%m.%Y')} - {data['date_to'].strftime('%d.%m.%Y')}\n"
        f"📦 <b>Тип поставки:</b> {supply_type_text}\n"
        f"🚚 <b>Тип доставки:</b> {delivery_type_text}\n"
        f"🤖 <b>Режим:</b> {mode_text}\n\n"
        "Выберите максимальный коэффициент приемки:"
    )
    
    await callback.message.edit_text(
        step_text,
        parse_mode="HTML",
        reply_markup=get_coefficient_keyboard()
    )
    await state.set_state(MonitoringStates.waiting_for_max_coefficient)
    await callback.answer()


@router.callback_query(
    SettingsCallback.filter(F.action == "coefficient"),
    StateFilter(MonitoringStates.waiting_for_max_coefficient)
)
async def handle_coefficient_selection(
    callback: CallbackQuery,
    callback_data: SettingsCallback,
    state: FSMContext
):
    """Handle coefficient selection."""
    max_coefficient = float(callback_data.value)
    await state.update_data(max_coefficient=max_coefficient)
    
    data = await state.get_data()
    
    mode_text = "🔔 Только уведомления" if data['monitoring_mode'] == "notification" else "🤖 Автобронирование"
    delivery_type_text = "🚚 Прямая" if data['delivery_type'] == "direct" else "🔄 Транзитная"
    supply_type_text = "📦 Короб" if data['supply_type'] == "box" else "🏗 Монопаллета"
    
    # Show final confirmation
    confirmation_text = (
        f"✅ <b>Подтверждение создания мониторинга</b>\n\n"
        f"📦 <b>Склад:</b> {data['warehouse_name']} (ID: {data['warehouse_id']})\n"
        f"📅 <b>Период:</b> {data['date_from'].strftime('%d.%m.%Y')} - {data['date_to'].strftime('%d.%m.%Y')}\n"
        f"📦 <b>Тип поставки:</b> {supply_type_text}\n"
        f"🚚 <b>Тип доставки:</b> {delivery_type_text}\n"
        f"🤖 <b>Режим:</b> {mode_text}\n"
        f"📊 <b>Макс. коэффициент:</b> {max_coefficient}x\n"
        f"⏱ <b>Интервал проверки:</b> {data['check_interval']} сек\n\n"
        "Создать мониторинг?"
    )
    
    await callback.message.edit_text(
        confirmation_text,
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard("create_monitoring")
    )
    await state.set_state(MonitoringStates.waiting_for_confirmation)
    await callback.answer()


@router.callback_query(
    F.data == "confirm_create_monitoring_0",
    StateFilter(MonitoringStates.waiting_for_confirmation)
)
async def create_monitoring_task(callback: CallbackQuery, state: FSMContext):
    """Create the monitoring task."""
    data = await state.get_data()
    user_id = callback.from_user.id
    user_logger = UserLogger(user_id)
    
    try:
        async with get_session() as session:
            # Create monitoring task
            monitoring_task = MonitoringTask(
                user_id=user_id,
                warehouse_id=data['warehouse_id'],
                warehouse_name=data['warehouse_name'],
                date_from=data['date_from'],
                date_to=data['date_to'],
                supply_type=data['supply_type'],
                delivery_type=data['delivery_type'],
                monitoring_mode=data['monitoring_mode'],
                max_coefficient=data['max_coefficient'],
                check_interval=data['check_interval'],
                is_active=True
            )
            
            session.add(monitoring_task)
            await session.commit()
            
            user_logger.info(f"Created monitoring task {monitoring_task.id}")
            
            success_text = (
                f"🎉 <b>Мониторинг создан успешно!</b>\n\n"
                f"🆔 <b>ID задачи:</b> {monitoring_task.id}\n"
                f"📦 <b>Склад:</b> {data['warehouse_name']}\n"
                f"📅 <b>Период:</b> {data['date_from'].strftime('%d.%m.%Y')} - {data['date_to'].strftime('%d.%m.%Y')}\n\n"
                f"🟢 Мониторинг запущен и активен!\n"
                f"Вы будете получать уведомления о найденных слотах."
            )
            
            await callback.message.edit_text(
                success_text,
                parse_mode="HTML",
                reply_markup=get_monitoring_menu()
            )
            
    except Exception as e:
        user_logger.error(f"Failed to create monitoring task: {e}")
        
        error_text = (
            "❌ <b>Ошибка создания мониторинга</b>\n\n"
            "Произошла ошибка при создании задачи. "
            "Попробуйте еще раз или обратитесь в поддержку."
        )
        
        await callback.message.edit_text(
            error_text,
            parse_mode="HTML",
            reply_markup=get_monitoring_menu()
        )
    
    await state.clear()
    await callback.answer()


@router.callback_query(MonitoringCallback.filter(F.action == "list"))
async def list_monitoring_tasks(callback: CallbackQuery):
    """Show list of user's monitoring tasks."""
    user_id = callback.from_user.id
    
    async with get_session() as session:
        query = select(MonitoringTask).where(
            MonitoringTask.user_id == user_id
        ).order_by(MonitoringTask.created_at.desc())
        
        result = await session.execute(query)
        tasks = result.scalars().all()
    
    if not tasks:
        no_tasks_text = (
            "📊 <b>Мониторинг слотов</b>\n\n"
            "У вас нет активных мониторингов.\n"
            "Создайте первый мониторинг для начала работы."
        )
        
        await callback.message.edit_text(
            no_tasks_text,
            parse_mode="HTML",
            reply_markup=get_monitoring_menu()
        )
        await callback.answer()
        return
    
    tasks_text = (
        f"📊 <b>Ваши мониторинги ({len(tasks)})</b>\n\n"
        "Выберите мониторинг для управления:"
    )
    
    await callback.message.edit_text(
        tasks_text,
        parse_mode="HTML",
        reply_markup=get_monitoring_list_keyboard(tasks)
    )
    await callback.answer()


@router.callback_query(MonitoringCallback.filter(F.action == "edit"))
async def show_monitoring_task(callback: CallbackQuery, callback_data: MonitoringCallback):
    """Show specific monitoring task details."""
    user_id = callback.from_user.id
    task_id = callback_data.task_id
    
    async with get_session() as session:
        query = select(MonitoringTask).where(
            and_(
                MonitoringTask.id == task_id,
                MonitoringTask.user_id == user_id
            )
        )
        result = await session.execute(query)
        task = result.scalar_one_or_none()
    
    if not task:
        await callback.answer("❌ Мониторинг не найден", show_alert=True)
        return
    
    status_emoji = "🟢" if task.is_active and not task.is_paused else "🔴" if task.is_paused else "⚪"
    mode_text = "🤖 Автобронирование" if task.monitoring_mode == "auto_booking" else "🔔 Уведомления"
    supply_type_text = "📦 Короб" if task.supply_type == "box" else "🏗 Монопаллета"
    delivery_type_text = "🚚 Прямая" if task.delivery_type == "direct" else "🔄 Транзитная"
    
    last_check = task.last_check.strftime('%d.%m.%Y %H:%M') if task.last_check else "Никогда"
    
    task_info_text = (
        f"📊 <b>Мониторинг #{task.id}</b>\n\n"
        f"📦 <b>Склад:</b> {task.warehouse_name}\n"
        f"📅 <b>Период:</b> {task.date_from.strftime('%d.%m.%Y')} - {task.date_to.strftime('%d.%m.%Y')}\n"
        f"📦 <b>Тип поставки:</b> {supply_type_text}\n"
        f"🚚 <b>Тип доставки:</b> {delivery_type_text}\n"
        f"🤖 <b>Режим:</b> {mode_text}\n"
        f"📊 <b>Макс. коэффициент:</b> {task.max_coefficient}x\n"
        f"⏱ <b>Интервал:</b> {task.check_interval} сек\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"🔍 Проверок: {task.total_checks}\n"
        f"📦 Найдено слотов: {task.slots_found}\n"
        f"✅ Успешных броней: {task.successful_bookings}\n"
        f"❌ Неудачных броней: {task.failed_bookings}\n\n"
        f"📊 <b>Статус:</b> {status_emoji} {'Активен' if task.is_active and not task.is_paused else 'Приостановлен' if task.is_paused else 'Неактивен'}\n"
        f"⏰ <b>Последняя проверка:</b> {last_check}"
    )
    
    await callback.message.edit_text(
        task_info_text,
        parse_mode="HTML",
        reply_markup=get_monitoring_task_keyboard(task)
    )
    await callback.answer()


@router.callback_query(MonitoringCallback.filter(F.action.in_(["pause", "resume"])))
async def toggle_monitoring_task(callback: CallbackQuery, callback_data: MonitoringCallback):
    """Pause or resume monitoring task."""
    user_id = callback.from_user.id
    task_id = callback_data.task_id
    action = callback_data.action
    
    user_logger = UserLogger(user_id)
    
    # Import monitoring service here to avoid circular imports
    from ...services.monitoring import monitoring_service
    
    if action == "pause":
        await monitoring_service.pause_task(task_id)
        user_logger.info(f"Paused monitoring task {task_id}")
        message = "⏸ Мониторинг приостановлен"
    else:
        await monitoring_service.resume_task(task_id)
        user_logger.info(f"Resumed monitoring task {task_id}")
        message = "▶️ Мониторинг возобновлен"
    
    await callback.answer(message)
    
    # Refresh the task view
    await show_monitoring_task(callback, callback_data)


@router.callback_query(MonitoringCallback.filter(F.action == "back"))
async def back_to_monitoring_menu(callback: CallbackQuery):
    """Return to monitoring main menu."""
    await callback.message.edit_text(
        "📊 <b>Мониторинг слотов</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_monitoring_menu()
    )
    await callback.answer()
