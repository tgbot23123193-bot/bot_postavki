"""
Простой обработчик мониторинга без использования БД.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

from ...utils.logger import get_logger

logger = get_logger(__name__)

router = Router(name="monitoring_simple")

# Константы для пагинации
WAREHOUSES_PER_PAGE = 5

# In-memory хранилище для задач мониторинга
user_monitoring_tasks = {}

# Временное хранилище данных пагинации
user_pagination_data = {}


class MonitoringCallback(CallbackData, prefix="mon"):
    """Callback data для мониторинга."""
    action: str
    value: str = ""


async def show_monitoring_options(callback: CallbackQuery):
    """Показать опции мониторинга."""
    text = (
        "🔍 <b>Мониторинг слотов</b>\n\n"
        "Выберите действие:\n\n"
        "🚀 <b>Быстрый поиск</b> - мгновенный поиск по всем складам\n"
        "⚡ <b>Автобронирование</b> - автоматический поиск и бронирование"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Быстрый поиск", callback_data="quick_search")],
        [InlineKeyboardButton(text="⚡ Автобронирование", callback_data="auto_booking")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "quick_search")
async def quick_search_handler(callback: CallbackQuery):
    """Быстрый поиск слотов."""
    logger.info(f"🚀 БЫСТРЫЙ ПОИСК ЗАПУЩЕН для пользователя {callback.from_user.id}")
    await callback.answer()  # Отвечаем на callback сразу
    
    from .callbacks import get_user_api_keys_list
    
    user_id = callback.from_user.id
    api_keys = await get_user_api_keys_list(user_id)
    
    logger.info(f"🔑 Найдено API ключей: {len(api_keys)}")
    
    if not api_keys:
        await callback.message.edit_text(
            "❌ <b>API ключ не найден!</b>\n\n"
            "Добавьте API ключ в настройках.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="monitoring")]
            ])
        )
        return
    
    # Показываем сообщение о сборе данных
    loading_msg = await callback.message.edit_text(
        "🔍 <b>Собираю данные по поставкам...</b>\n\n"
        "⏳ Это может занять до 2 минут\n"
        "📊 Анализирую доступные склады и слоты...",
        parse_mode="HTML"
    )
    
    try:
        from ...services.wb_supplies_api import WBSuppliesAPIClient
        
        logger.info(f"🚀 Начинаю быстрый поиск для пользователя {user_id}")
        
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            # Получаем все склады
            logger.info("🏬 Получаю список всех складов...")
            warehouses = await api_client.get_warehouses()
            
            if not warehouses:
                await loading_msg.edit_text(
                    "❌ <b>Склады не найдены</b>\n\n"
                    "Проверьте API ключ и попробуйте позже.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="monitoring")]
                    ])
                )
                return
            
            # Берем топ-30 складов для быстрого поиска
            top_warehouses = warehouses[:30]
            warehouse_ids = [wh.get('id') for wh in top_warehouses if wh.get('id')]
            
            logger.info(f"📊 Получаю коэффициенты приёмки для {len(warehouse_ids)} складов...")
            available_slots = await api_client.get_acceptance_coefficients(warehouse_ids)
            
            logger.info(f"✅ Найдено {len(available_slots)} доступных слотов")
            
        # Группируем слоты по складам
        slots_by_warehouse = {}
        for slot in available_slots:
            wh_id = slot.get("warehouseID")
            if wh_id not in slots_by_warehouse:
                slots_by_warehouse[wh_id] = []
            slots_by_warehouse[wh_id].append(slot)
        
        # Сохраняем данные для пагинации
        user_id = callback.from_user.id
        user_pagination_data[user_id] = {
            'warehouses': warehouses,
            'available_slots': available_slots,
            'slots_by_warehouse': slots_by_warehouse
        }
        
        # Отображаем первую страницу
        await show_warehouses_page(loading_msg, 0, warehouses, available_slots, slots_by_warehouse)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в быстром поиске: {type(e).__name__}: {str(e)}")
        await loading_msg.edit_text(
            "❌ <b>Ошибка при поиске слотов</b>\n\n"
            "Проверьте подключение к интернету и попробуйте позже.\n"
            f"<i>Детали: {str(e)[:100]}...</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="quick_search")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="monitoring")]
            ])
        )


@router.callback_query(F.data == "my_tasks")
async def show_my_tasks(callback: CallbackQuery):
    """Показать задачи мониторинга пользователя."""
    user_id = callback.from_user.id
    tasks = user_monitoring_tasks.get(user_id, [])
    
    if not tasks:
        text = (
            "📊 <b>У вас нет активных задач</b>\n\n"
            "Создайте задачу мониторинга для автоматического отслеживания слотов."
        )
    else:
        text = f"📊 <b>Ваши задачи ({len(tasks)} шт.)</b>\n\n"
        for i, task in enumerate(tasks, 1):
            text += f"{i}. {task.get('name', 'Задача')} - {task.get('status', 'Активна')}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать задачу", callback_data="create_task")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="monitoring")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "create_task")
async def create_task_handler(callback: CallbackQuery):
    """Создать новую задачу мониторинга."""
    await callback.answer("🚧 Функция в разработке", show_alert=True)


async def show_warehouses_page(message, page: int, warehouses, available_slots, slots_by_warehouse):
    """Отображает страницу складов с пагинацией."""
    # Фильтруем только склады с доступными слотами
    warehouses_with_slots = [w for w in warehouses if w.get('id') in slots_by_warehouse]
    
    total_pages = (len(warehouses_with_slots) + WAREHOUSES_PER_PAGE - 1) // WAREHOUSES_PER_PAGE
    start_idx = page * WAREHOUSES_PER_PAGE
    end_idx = min(start_idx + WAREHOUSES_PER_PAGE, len(warehouses_with_slots))
    
    if available_slots:
        text = f"🎯 <b>Найдено доступных слотов: {len(available_slots)}</b>\n\n"
        text += f"📄 Страница {page + 1} из {total_pages} (складов со слотами: {len(warehouses_with_slots)})\n\n"
        
        # Показываем склады текущей страницы
        for i in range(start_idx, end_idx):
            warehouse = warehouses_with_slots[i]
            wh_id = warehouse.get('id')
            wh_name = warehouse.get('name', f'Склад #{wh_id}')
            
            slots = slots_by_warehouse.get(wh_id, [])
            text += f"🏬 <b>{wh_name}</b>\n"
            text += f"   🆔 ID: {wh_id}\n"
            text += f"   🎯 Доступно слотов: {len(slots)}\n"
            
            # Показываем ближайшие даты
            dates = [slot.get("date", "").split("T")[0] for slot in slots[:3]]
            if dates:
                text += f"   📅 Ближайшие даты: {', '.join(dates)}\n"
            
            text += "\n"
    else:
        text = f"🏬 <b>Найдено складов: {len(warehouses)}</b>\n\n"
        text += "⚠️ <b>Доступных слотов не найдено</b>\n\n"
        text += "На ближайшие 14 дней нет свободных слотов для бронирования.\n"
        text += "Попробуйте позже или используйте автоматический мониторинг.\n\n"
        
    text += "💡 <i>Для бронирования используйте 'Управление поставками'</i>"
    
    # Создаем клавиатуру с пагинацией
    keyboard = []
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"warehouses_page:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"warehouses_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Основные кнопки
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Обновить склады", callback_data="quick_search")],
        [InlineKeyboardButton(text="📦 Управление поставками", callback_data="view_supplies")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="monitoring")]
    ])
    
    await message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("warehouses_page:"))
async def show_warehouses_page_handler(callback: CallbackQuery):
    """Обработчик пагинации складов."""
    await callback.answer()  # Отвечаем на callback сразу
    
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем сохраненные данные
    if user_id in user_pagination_data:
        data = user_pagination_data[user_id]
        warehouses = data['warehouses']
        available_slots = data['available_slots']
        slots_by_warehouse = data['slots_by_warehouse']
        
        await show_warehouses_page(callback.message, page, warehouses, available_slots, slots_by_warehouse)
    else:
        await callback.answer("❌ Данные устарели, выполните поиск заново", show_alert=True)


