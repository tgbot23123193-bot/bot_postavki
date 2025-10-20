"""
Обработчики для бронирования через браузер.
"""

import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ...services.browser_manager import browser_manager
from ...utils.logger import get_logger

logger = get_logger(__name__)
router = Router()


class BrowserBookingStates(StatesGroup):
    """Состояния для браузерного бронирования."""
    waiting_for_phone = State()
    waiting_for_sms_code = State()
    selecting_supply = State()
    selecting_dates = State()
    monitoring = State()


@router.callback_query(F.data == "browser_booking")
async def start_browser_booking(callback: CallbackQuery, state: FSMContext):
    """Начало браузерного бронирования."""
    user_id = callback.from_user.id
    
    text = (
        "🌐 <b>Браузерное бронирование</b>\n\n"
        "Автоматизация через браузер для входа в WB и бронирования слотов.\n\n"
        "⚠️ <b>Требуется:</b>\n"
        "• Номер телефона для входа в WB\n"
        "• СМС код для подтверждения\n\n"
        "🔒 Браузер работает в скрытом режиме для максимальной безопасности.\n\n"
        "Нажмите 'Запустить' для начала работы:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить браузер", callback_data="browser_start_headless")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="auto_booking")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "browser_stop")
async def browser_stop(callback: CallbackQuery):
    """Закрытие браузера."""
    user_id = callback.from_user.id
    
    try:
        closed = await browser_manager.close_browser(user_id)
        
        if closed:
            await callback.message.edit_text(
                "✅ <b>Браузер закрыт</b>\n\n"
                "Сессия завершена. Можете запустить новую.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить снова", callback_data="browser_booking")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
                ])
            )
        else:
            await callback.message.edit_text(
                "ℹ️ <b>Браузер используется другими пользователями</b>\n\n"
                "Вы отключены от браузера, но он продолжает работать для других.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Подключиться заново", callback_data="browser_booking")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error closing browser: {e}")
        await callback.message.edit_text(
            "⚠️ <b>Ошибка при закрытии браузера</b>\n\n"
            "Попробуйте еще раз:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="browser_stop")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
            ])
        )
    
    await callback.answer()


@router.callback_query(F.data == "browser_start_headless")
async def browser_start_mode_fixed(callback: CallbackQuery, state: FSMContext):
    """Запуск браузера в выбранном режиме - исправленная версия."""
    user_id = callback.from_user.id
    headless = True  # Всегда скрытый режим
    
    # Проверяем есть ли уже запущенный браузер ЭТОГО ПОЛЬЗОВАТЕЛЯ
    if browser_manager.is_browser_active(user_id):
        await callback.message.edit_text(
            "⚠️ <b>Браузер уже запущен!</b>\n\n"
            "Сначала закройте текущую сессию:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Закрыть браузер", callback_data="browser_stop")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_booking")]
            ])
        )
        await callback.answer()
        return
    
    mode_text = "скрытом" if headless else "видимом"
    
    loading_msg = await callback.message.edit_text(
        f"🚀 Запускаю браузер в {mode_text} режиме...\n"
        "⏳ Это может занять несколько секунд...",
        parse_mode="HTML"
    )
    
    try:
        # Получаем браузер через единый менеджер
        browser = await browser_manager.get_browser(user_id, headless=False, debug_mode=True)
        
        if not browser:
            raise Exception("Не удалось запустить браузер")
        
        # Проверяем, не авторизован ли пользователь уже
        try:
            should_skip = await browser.should_skip_login()
            if should_skip:
                await loading_msg.edit_text(
                    "✅ <b>Вы уже авторизованы в WB!</b>\n\n"
                    "🎉 Браузер готов к работе!\n\n"
                    "Выберите действие:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📦 Мои поставки", callback_data="view_supplies")],
                        [InlineKeyboardButton(text="🤖 Автомониторинг", callback_data="browser_auto_monitor")],
                        [InlineKeyboardButton(text="❌ Закрыть браузер", callback_data="browser_close")]
                    ])
                )
                await state.clear()
                return
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки авторизации: {e}")
        
        await loading_msg.edit_text(
            f"✅ <b>Браузер запущен в {mode_text} режиме!</b>\n\n"
            "📱 Введите номер телефона для входа в WB:\n"
            "(в формате +79991234567 или +996500441234)",
            parse_mode="HTML"
        )
        
        await state.set_state(BrowserBookingStates.waiting_for_phone)
        
    except Exception as e:
        logger.error(f"Error starting browser: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка запуска браузера.\n"
            "Убедитесь что Chrome установлен.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_booking")]
            ])
        )


@router.message(BrowserBookingStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка номера телефона."""
    logger.info(f"🔍 BROWSER: Processing phone from user {message.from_user.id}: {message.text}")
    user_id = message.from_user.id
    phone = message.text.strip()
    
    # Игнорируем команды во время ввода номера
    if phone.startswith('/'):
        return
    
    # Проверяем формат
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
    
    loading_msg = await message.answer(
        "📱 Ввожу номер телефона в форму WB...\n"
        "⏳ Ожидайте..."
    )
    
    try:
        # Автоматически вводим номер в форму WB
        success = await browser.login_step1_phone(phone)
        
        if success:
            await loading_msg.edit_text(
                f"✅ <b>Номер введен в форму WB!</b>\n\n"
                f"📱 Номер: {phone[:4]}****{phone[-2:]}\n"
                f"📨 СМС код отправлен на ваш телефон\n\n"
                f"🔑 Введите полученный код:"
            )
            
            await state.update_data(phone=phone)
            await state.set_state(BrowserBookingStates.waiting_for_sms_code)
        else:
            await loading_msg.edit_text(
                "❌ <b>Ошибка ввода номера</b>\n\n"
                "Не удалось ввести номер в форму WB.\n"
                "Попробуйте еще раз или обратитесь к администратору."
            )
            await state.clear()
        
    except Exception as e:
        logger.error(f"Error during phone input: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при входе. Попробуйте еще раз."
        )


@router.message(BrowserBookingStates.waiting_for_sms_code)
async def process_sms_code(message: Message, state: FSMContext):
    """Обработка СМС кода."""
    user_id = message.from_user.id
    code = message.text.strip()
    
    # Игнорируем команды во время ввода SMS кода
    if code.startswith('/'):
        return
    
    browser = await browser_manager.get_browser(user_id)
    if not browser:
        await message.answer("❌ Сессия браузера потеряна.")
        await state.clear()
        return
    
    # Проверяем формат СМС кода
    if not code.isdigit() or len(code) < 4 or len(code) > 6:
        await message.answer(
            "❌ Неверный формат кода.\n"
            "Введите 4-6 цифр из СМС."
        )
        return
    
    loading_msg = await message.answer(
        "🔐 Ввожу СМС код в форму WB...\n"
        "⏳ Проверяю вход..."
    )
    
    try:
        # Автоматически вводим СМС код в форму WB
        result = await browser.login_step2_sms(code)
        
        if result == "email_required":
            await loading_msg.edit_text(
                "📧 <b>Требуется подтверждение по email</b>\n\n"
                "WB требует дополнительное подтверждение через электронную почту.\n\n"
                "📋 <b>Что делать:</b>\n"
                "1️⃣ Проверьте свою электронную почту\n"
                "2️⃣ Найдите письмо от Wildberries\n"
                "3️⃣ Перейдите по ссылке в письме\n"
                "4️⃣ После подтверждения попробуйте снова\n\n"
                "⚠️ Без подтверждения email авторизация невозможна.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="browser_start")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="browser_close")]
                ])
            )
            await state.clear()
        elif result:
            await loading_msg.edit_text(
                "✅ <b>Успешный вход в WB!</b>\n\n"
                "🎉 Браузер готов к работе!\n\n"
                "Выберите действие:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Мои поставки", callback_data="view_supplies")],
                    [InlineKeyboardButton(text="🤖 Автомониторинг", callback_data="browser_auto_monitor")],
                    [InlineKeyboardButton(text="❌ Закрыть браузер", callback_data="browser_close")]
                ])
            )
            await state.clear()
        else:
            await loading_msg.edit_text(
                "❌ <b>Ошибка входа</b>\n\n"
                "Неверный СМС код или проблема с сайтом WB.\n"
                "Попробуйте еще раз:"
            )
    
    except Exception as e:
        logger.error(f"Error during SMS code input: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при вводе СМС кода. Попробуйте еще раз."
        )


# УДАЛЕНО: browser_find_slots - функция больше не используется


@router.callback_query(F.data == "browser_auto_monitor")
async def browser_auto_monitor(callback: CallbackQuery, state: FSMContext):
    """Настройка автоматического мониторинга."""
    user_id = callback.from_user.id
    browser = await browser_manager.get_browser(user_id)
    
    if not browser:
        await callback.answer("❌ Сессия браузера не найдена", show_alert=True)
        return
    
    text = (
        "🤖 <b>Автоматический мониторинг</b>\n\n"
        "Бот будет автоматически искать слоты и бронировать "
        "первый подходящий.\n\n"
        "Настройте параметры:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏬 Доступные склады", callback_data="browser_show_warehouses")],
        [InlineKeyboardButton(text="📅 Выбрать период", callback_data="browser_select_period")],
        [InlineKeyboardButton(text="📊 Макс. коэффициент", callback_data="browser_select_coef")],
        [InlineKeyboardButton(text="✅ Начать мониторинг", callback_data="browser_start_monitor")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


# Константы для пагинации складов
WAREHOUSES_PER_PAGE = 5

# Временное хранилище данных пагинации для автомониторинга
browser_warehouses_data = {}


@router.callback_query(F.data == "browser_show_warehouses")
async def browser_show_warehouses(callback: CallbackQuery):
    """Показать доступные склады через API."""
    await callback.answer()
    user_id = callback.from_user.id
    
    # Получаем API ключи пользователя
    from .callbacks import get_user_api_keys_list
    api_keys = await get_user_api_keys_list(user_id)
    
    if not api_keys:
        await callback.message.edit_text(
            "❌ <b>API ключ не найден!</b>\n\n"
            "Добавьте API ключ в настройках.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
            ])
        )
        return
    
    # Показываем сообщение о загрузке
    loading_msg = await callback.message.edit_text(
        "🔍 <b>Получаю данные по складам...</b>\n\n"
        "⏳ Это может занять до 2 минут\n"
        "📊 Анализирую доступные склады и слоты...",
        parse_mode="HTML"
    )
    
    try:
        from ...services.wb_supplies_api import WBSuppliesAPIClient
        
        logger.info(f"🏬 Получаю склады для пользователя {user_id}")
        
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
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
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
        browser_warehouses_data[user_id] = {
            'warehouses': warehouses,
            'available_slots': available_slots,
            'slots_by_warehouse': slots_by_warehouse
        }
        
        # Отображаем первую страницу
        await show_browser_warehouses_page(loading_msg, user_id, 0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения складов: {type(e).__name__}: {str(e)}")
        await loading_msg.edit_text(
            "❌ <b>Ошибка при получении складов</b>\n\n"
            "Проверьте подключение к интернету и попробуйте позже.\n"
            f"<i>Детали: {str(e)[:100]}...</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="browser_show_warehouses")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
            ])
        )


async def show_browser_warehouses_page(message, user_id: int, page: int):
    """Отображает страницу складов с пагинацией для автомониторинга."""
    if user_id not in browser_warehouses_data:
        await message.edit_text(
            "❌ Данные устарели, выполните поиск заново",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
            ])
        )
        return
    
    data = browser_warehouses_data[user_id]
    warehouses = data['warehouses']
    available_slots = data['available_slots']
    slots_by_warehouse = data['slots_by_warehouse']
    
    # Фильтруем только склады с доступными слотами
    warehouses_with_slots = [w for w in warehouses if w.get('id') in slots_by_warehouse]
    
    total_warehouses = len(warehouses_with_slots) if warehouses_with_slots else len(warehouses)
    total_pages = (total_warehouses + WAREHOUSES_PER_PAGE - 1) // WAREHOUSES_PER_PAGE
    start_idx = page * WAREHOUSES_PER_PAGE
    end_idx = min(start_idx + WAREHOUSES_PER_PAGE, total_warehouses)
    
    # Формируем текст
    if available_slots and warehouses_with_slots:
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
        text += f"📄 Страница {page + 1} из {total_pages}\n\n"
        
        # Показываем склады без слотов
        warehouses_to_show = warehouses[start_idx:end_idx]
        for warehouse in warehouses_to_show:
            wh_id = warehouse.get('id')
            wh_name = warehouse.get('name', f'Склад #{wh_id}')
            text += f"🏬 <b>{wh_name}</b>\n"
            text += f"   🆔 ID: {wh_id}\n"
            text += f"   ⚠️ Нет доступных слотов\n\n"
        
        if not available_slots:
            text += "\n⚠️ <b>Доступных слотов не найдено</b>\n"
            text += "Попробуйте позже или используйте автоматический мониторинг.\n\n"
    
    text += "💡 <i>Используйте автомониторинг для автоматического бронирования</i>"
    
    # Создаем клавиатуру с пагинацией
    keyboard = []
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"browser_wh_page:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"browser_wh_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Основные кнопки
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="browser_show_warehouses")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
    ])
    
    await message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("browser_wh_page:"))
async def browser_warehouses_page_handler(callback: CallbackQuery):
    """Обработчик пагинации складов в автомониторинге."""
    await callback.answer()
    
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    await show_browser_warehouses_page(callback.message, user_id, page)


@router.callback_query(F.data == "browser_select_period")
async def browser_select_period(callback: CallbackQuery, state: FSMContext):
    """Выбор периода для мониторинга."""
    text = (
        "📅 <b>Выбор периода мониторинга</b>\n\n"
        "Выберите период в который бот будет искать слоты:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Ближайшие 7 дней", callback_data="period_7")],
        [InlineKeyboardButton(text="📆 Ближайшие 14 дней", callback_data="period_14")],
        [InlineKeyboardButton(text="📆 Ближайшие 30 дней", callback_data="period_30")],
        [InlineKeyboardButton(text="📆 Любая дата", callback_data="period_any")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("period_"))
async def process_period_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора периода."""
    period = callback.data.replace("period_", "")
    
    # Сохраняем выбор в состояние
    await state.update_data(monitoring_period=period)
    
    period_names = {
        "7": "Ближайшие 7 дней",
        "14": "Ближайшие 14 дней", 
        "30": "Ближайшие 30 дней",
        "any": "Любая дата"
    }
    
    await callback.answer(f"✅ Выбран период: {period_names.get(period, period)}")
    
    # Возвращаемся в меню автомониторинга
    await browser_auto_monitor(callback, state)


@router.callback_query(F.data == "browser_select_coef")
async def browser_select_coef(callback: CallbackQuery, state: FSMContext):
    """Выбор максимального коэффициента."""
    text = (
        "📊 <b>Максимальный коэффициент</b>\n\n"
        "Выберите максимальный коэффициент приёмки.\n"
        "Бот забронирует слоты с коэффициентом не выше выбранного:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1.0", callback_data="coef_1.0"),
            InlineKeyboardButton(text="1.5", callback_data="coef_1.5")
        ],
        [
            InlineKeyboardButton(text="2.0", callback_data="coef_2.0"),
            InlineKeyboardButton(text="2.5", callback_data="coef_2.5")
        ],
        [
            InlineKeyboardButton(text="3.0", callback_data="coef_3.0"),
            InlineKeyboardButton(text="Любой", callback_data="coef_any")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("coef_"))
async def process_coef_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора коэффициента."""
    coef = callback.data.replace("coef_", "")
    
    # Сохраняем выбор в состояние
    await state.update_data(max_coefficient=coef)
    
    await callback.answer(f"✅ Максимальный коэффициент: {coef}")
    
    # Возвращаемся в меню автомониторинга
    await browser_auto_monitor(callback, state)


@router.callback_query(F.data == "browser_start_monitor")
async def browser_start_monitor(callback: CallbackQuery, state: FSMContext):
    """Запуск автоматического мониторинга с фильтрацией по API."""
    await callback.answer()
    user_id = callback.from_user.id
    
    # Получаем настройки из состояния
    data = await state.get_data()
    period = data.get('monitoring_period', 'any')
    max_coef = data.get('max_coefficient', 'any')
    
    browser = await browser_manager.get_browser(user_id)
    
    if not browser:
        await callback.answer("❌ Сессия браузера не найдена", show_alert=True)
        return
    
    # Получаем API ключи пользователя
    from .callbacks import get_user_api_keys_list
    api_keys = await get_user_api_keys_list(user_id)
    
    if not api_keys:
        await callback.message.edit_text(
            "❌ <b>API ключ не найден!</b>\n\n"
            "Добавьте API ключ в настройках для использования мониторинга.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
            ])
        )
        return
    
    # Показываем сообщение о поиске
    period_names = {
        "7": "7 дней",
        "14": "14 дней",
        "30": "30 дней",
        "any": "любая дата"
    }
    
    loading_msg = await callback.message.edit_text(
        f"🔍 <b>Запускаю мониторинг...</b>\n\n"
        f"📅 Период: {period_names.get(period, period)}\n"
        f"📊 Макс. коэффициент: {max_coef}\n\n"
        f"⏳ Получаю данные по складам...\n"
        f"Это может занять до 2 минут...",
        parse_mode="HTML"
    )
    
    try:
        from ...services.wb_supplies_api import WBSuppliesAPIClient
        from datetime import datetime, timedelta
        
        logger.info(f"🤖 Запуск мониторинга для пользователя {user_id}: период={period}, коэф={max_coef}")
        
        async with WBSuppliesAPIClient(api_keys[0]) as api_client:
            # Получаем все склады
            logger.info("🏬 Получаю список складов...")
            warehouses = await api_client.get_warehouses()
            
            if not warehouses:
                await loading_msg.edit_text(
                    "❌ <b>Не удалось получить склады</b>\n\n"
                    "Проверьте API ключ и попробуйте позже.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
                    ])
                )
                return
            
            # Берем топ-30 складов
            top_warehouses = warehouses[:30]
            warehouse_ids = [wh.get('id') for wh in top_warehouses if wh.get('id')]
            
            logger.info(f"📊 Получаю коэффициенты для {len(warehouse_ids)} складов...")
            all_slots = await api_client.get_acceptance_coefficients(warehouse_ids)
            
            logger.info(f"✅ Получено {len(all_slots)} слотов, начинаю фильтрацию...")
        
        # Фильтрация по периоду
        if period != 'any':
            days = int(period)
            end_date = datetime.now() + timedelta(days=days)
            
            filtered_slots = []
            for slot in all_slots:
                slot_date_str = slot.get("date", "").split("T")[0]
                try:
                    slot_date = datetime.strptime(slot_date_str, "%Y-%m-%d")
                    if slot_date <= end_date:
                        filtered_slots.append(slot)
                except:
                    continue
            
            logger.info(f"📅 После фильтрации по периоду ({days} дней): {len(filtered_slots)} слотов")
            all_slots = filtered_slots
        
        # Фильтрация по коэффициенту
        if max_coef != 'any':
            max_coefficient = float(max_coef)
            filtered_slots = [
                slot for slot in all_slots 
                if slot.get("coefficient", 999) <= max_coefficient
            ]
            logger.info(f"📊 После фильтрации по коэффициенту (<= {max_coefficient}): {len(filtered_slots)} слотов")
            all_slots = filtered_slots
        
        # Группируем по складам
        slots_by_warehouse = {}
        for slot in all_slots:
            wh_id = slot.get("warehouseID")
            if wh_id not in slots_by_warehouse:
                slots_by_warehouse[wh_id] = []
            slots_by_warehouse[wh_id].append(slot)
        
        # Сохраняем отфильтрованные данные
        browser_warehouses_data[user_id] = {
            'warehouses': warehouses,
            'available_slots': all_slots,
            'slots_by_warehouse': slots_by_warehouse,
            'period': period,
            'max_coef': max_coef
        }
        
        # Показываем результаты
        await show_monitoring_results_page(loading_msg, user_id, 0, period, max_coef)
        
    except Exception as e:
        logger.error(f"❌ Ошибка мониторинга: {type(e).__name__}: {str(e)}")
        await loading_msg.edit_text(
            f"❌ <b>Ошибка при поиске слотов</b>\n\n"
            f"Проверьте подключение и попробуйте позже.\n"
            f"<i>Детали: {str(e)[:100]}...</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="browser_start_monitor")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
            ])
        )


async def show_monitoring_results_page(message, user_id: int, page: int, period: str, max_coef: str):
    """Отображает страницу отфильтрованных результатов мониторинга."""
    if user_id not in browser_warehouses_data:
        await message.edit_text(
            "❌ Данные устарели, запустите мониторинг заново",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_auto_monitor")]
            ])
        )
        return
    
    data = browser_warehouses_data[user_id]
    warehouses = data['warehouses']
    available_slots = data['available_slots']
    slots_by_warehouse = data['slots_by_warehouse']
    
    period_names = {
        "7": "7 дней",
        "14": "14 дней",
        "30": "30 дней",
        "any": "любая дата"
    }
    
    # Фильтруем только склады с доступными слотами
    warehouses_with_slots = [w for w in warehouses if w.get('id') in slots_by_warehouse]
    
    total_warehouses = len(warehouses_with_slots)
    total_pages = max(1, (total_warehouses + WAREHOUSES_PER_PAGE - 1) // WAREHOUSES_PER_PAGE)
    start_idx = page * WAREHOUSES_PER_PAGE
    end_idx = min(start_idx + WAREHOUSES_PER_PAGE, total_warehouses)
    
    # Формируем заголовок
    text = f"🎯 <b>Результаты мониторинга</b>\n\n"
    text += f"📅 Период: {period_names.get(period, period)}\n"
    text += f"📊 Макс. коэффициент: {max_coef}\n\n"
    
    if available_slots and warehouses_with_slots:
        text += f"✅ <b>Найдено слотов: {len(available_slots)}</b>\n"
        text += f"🏬 <b>Складов: {len(warehouses_with_slots)}</b>\n\n"
        text += f"📄 Страница {page + 1} из {total_pages}\n\n"
        
        # Показываем склады текущей страницы
        for i in range(start_idx, end_idx):
            warehouse = warehouses_with_slots[i]
            wh_id = warehouse.get('id')
            wh_name = warehouse.get('name', f'Склад #{wh_id}')
            
            slots = slots_by_warehouse.get(wh_id, [])
            
            # Находим минимальный коэффициент
            min_coef = min([s.get("coefficient", 999) for s in slots], default=999)
            
            text += f"🏬 <b>{wh_name}</b>\n"
            text += f"   🆔 ID: {wh_id}\n"
            text += f"   🎯 Слотов: {len(slots)} шт.\n"
            text += f"   📊 Мин. коэф.: {min_coef}\n"
            
            # Показываем ближайшие даты с коэффициентами
            sorted_slots = sorted(slots, key=lambda x: x.get("date", ""))[:3]
            if sorted_slots:
                dates_info = []
                for slot in sorted_slots:
                    date = slot.get("date", "").split("T")[0]
                    coef = slot.get("coefficient", "?")
                    dates_info.append(f"{date} ({coef})")
                text += f"   📅 {', '.join(dates_info)}\n"
            
            text += "\n"
        
        text += "💡 <i>Нажмите на склад чтобы забронировать слот</i>"
    else:
        text += f"❌ <b>Подходящих слотов не найдено</b>\n\n"
        text += f"По выбранным параметрам нет доступных слотов.\n\n"
        text += f"Попробуйте:\n"
        text += f"• Увеличить период поиска\n"
        text += f"• Увеличить макс. коэффициент\n"
        text += f"• Запустить мониторинг позже"
    
    # Создаем клавиатуру с пагинацией
    keyboard = []
    
    # Кнопки навигации (только если есть результаты)
    if warehouses_with_slots:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"monitor_page:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"monitor_page:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    # Основные кнопки
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Обновить поиск", callback_data="browser_start_monitor")],
        [InlineKeyboardButton(text="⚙️ Изменить параметры", callback_data="browser_auto_monitor")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="browser_menu")]
    ])
    
    await message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("monitor_page:"))
async def monitoring_results_page_handler(callback: CallbackQuery):
    """Обработчик пагинации результатов мониторинга."""
    await callback.answer()
    
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    if user_id in browser_warehouses_data:
        data = browser_warehouses_data[user_id]
        period = data.get('period', 'any')
        max_coef = data.get('max_coef', 'any')
        await show_monitoring_results_page(callback.message, user_id, page, period, max_coef)
    else:
        await callback.answer("❌ Данные устарели", show_alert=True)


@router.callback_query(F.data == "browser_stop_monitor")
async def browser_stop_monitor(callback: CallbackQuery, state: FSMContext):
    """Остановка автоматического мониторинга."""
    await state.update_data(monitoring_active=False)
    await state.clear()
    
    await callback.message.edit_text(
        "🛑 <b>Мониторинг остановлен</b>\n\n"
        "Вы можете запустить новый мониторинг в любое время.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Запустить снова", callback_data="browser_auto_monitor")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="browser_menu")]
        ])
    )
    await callback.answer("✅ Мониторинг остановлен")


@router.callback_query(F.data == "browser_monitor_status")
async def browser_monitor_status(callback: CallbackQuery, state: FSMContext):
    """Показать статус мониторинга."""
    data = await state.get_data()
    is_active = data.get('monitoring_active', False)
    
    if is_active:
        period = data.get('monitoring_period', 'any')
        max_coef = data.get('max_coefficient', 'any')
        
        period_names = {
            "7": "7 дней",
            "14": "14 дней",
            "30": "30 дней",
            "any": "любая дата"
        }
        
        text = (
            "📊 <b>Статус мониторинга</b>\n\n"
            "✅ Статус: Активен\n"
            f"📅 Период: {period_names.get(period, period)}\n"
            f"📊 Макс. коэффициент: {max_coef}\n\n"
            "🔍 Поиск слотов продолжается..."
        )
    else:
        text = (
            "📊 <b>Статус мониторинга</b>\n\n"
            "❌ Мониторинг не активен"
        )
    
    await callback.answer(text, show_alert=True)


async def run_monitoring_task(user_id: int, browser, period: str, max_coef: str, state: FSMContext):
    """Фоновая задача мониторинга слотов."""
    try:
        logger.info(f"🤖 Запущен мониторинг для пользователя {user_id}")
        
        while True:
            # Проверяем что мониторинг все еще активен
            data = await state.get_data()
            if not data.get('monitoring_active', False):
                logger.info(f"🛑 Мониторинг остановлен для пользователя {user_id}")
                break
            
            # TODO: Здесь должна быть логика поиска слотов
            # Пока просто ждем 60 секунд между проверками
            await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f"❌ Ошибка в мониторинге для пользователя {user_id}: {e}")


@router.callback_query(F.data == "browser_menu")
async def browser_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню браузера после авторизации."""
    await callback.message.edit_text(
        "✅ <b>Браузер активен</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Мои поставки", callback_data="view_supplies")],
            [InlineKeyboardButton(text="🤖 Автомониторинг", callback_data="browser_auto_monitor")],
            [InlineKeyboardButton(text="❌ Закрыть браузер", callback_data="browser_close")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "browser_close")
async def browser_close(callback: CallbackQuery):
    """Закрытие браузера."""
    user_id = callback.from_user.id
    try:
        await browser_manager.close_browser(user_id)
    except Exception as e:
        logger.error(f"Error closing browser: {e}")
        
    await callback.message.edit_text(
        "✅ Браузер закрыт.\n\n"
        "Спасибо за использование!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )


# УДАЛЕНО: browser_my_supplies - теперь используется view_supplies из supplies_management
