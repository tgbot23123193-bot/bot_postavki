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
    
    # Проверяем есть ли уже запущенный браузер
    if browser_manager.is_browser_active():
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
                        [InlineKeyboardButton(text="🔍 Найти слоты", callback_data="browser_find_slots")],
                        [InlineKeyboardButton(text="📦 Мои поставки", callback_data="browser_my_supplies")],
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
                    [InlineKeyboardButton(text="🔍 Найти слоты", callback_data="browser_find_slots")],
                    [InlineKeyboardButton(text="📦 Мои поставки", callback_data="browser_my_supplies")],
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


@router.callback_query(F.data == "browser_find_slots")
async def browser_find_slots(callback: CallbackQuery):
    """Поиск доступных слотов через браузер."""
    user_id = callback.from_user.id
    browser = await browser_manager.get_browser(user_id)
    
    if not browser:
        await callback.answer("❌ Сессия браузера не найдена", show_alert=True)
        return
    
    loading_msg = await callback.message.edit_text(
        "🔍 Ищу доступные слоты...\n"
        "⏳ Это может занять несколько секунд...",
        parse_mode="HTML"
    )
    
    try:
        slots = await browser.find_available_slots()
        
        if slots:
            text = f"✅ <b>Найдено слотов: {len(slots)}</b>\n\n"
            
            for i, slot in enumerate(slots[:10], 1):
                text += f"{i}. 📅 {slot['date']} - Коэф: x{slot['coefficient']}\n"
            
            if len(slots) > 10:
                text += f"\n... и еще {len(slots) - 10} слотов"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Забронировать", callback_data="browser_book_slot")],
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="browser_find_slots")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
            ])
            
            await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await loading_msg.edit_text(
                "😔 Доступных слотов не найдено.\n"
                "Попробуйте позже или настройте автомониторинг.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Повторить", callback_data="browser_find_slots")],
                    [InlineKeyboardButton(text="🤖 Автомониторинг", callback_data="browser_auto_monitor")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error finding slots: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при поиске слотов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
            ])
        )


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
        [InlineKeyboardButton(text="📅 Выбрать период", callback_data="browser_select_period")],
        [InlineKeyboardButton(text="📊 Макс. коэффициент", callback_data="browser_select_coef")],
        [InlineKeyboardButton(text="✅ Начать мониторинг", callback_data="browser_start_monitor")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


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


@router.callback_query(F.data == "browser_my_supplies")
async def browser_my_supplies(callback: CallbackQuery):
    """Показать мои поставки через браузер."""
    user_id = callback.from_user.id
    browser = await browser_manager.get_browser(user_id)
    
    if not browser:
        await callback.answer("❌ Сессия браузера не найдена", show_alert=True)
        return
    
    loading_msg = await callback.message.edit_text(
        "📦 Загружаю ваши поставки...\n"
        "⏳ Это может занять несколько секунд...",
        parse_mode="HTML"
    )
    
    try:
        # Переходим на страницу поставок
        await browser.navigate_to_supplies_page()
        await asyncio.sleep(2)
        
        # Получаем список поставок
        supplies = await browser.get_my_supplies()
        
        if supplies:
            text = f"📦 <b>Ваши поставки ({len(supplies)} шт):</b>\n\n"
            
            for i, supply in enumerate(supplies[:10], 1):
                status = supply.get('status', 'Неизвестно')
                date = supply.get('date', 'Не указана')
                text += f"{i}. 🆔 #{supply.get('id', 'N/A')} - {status}\n"
                text += f"   📅 Дата: {date}\n\n"
            
            if len(supplies) > 10:
                text += f"... и еще {len(supplies) - 10} поставок"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="browser_my_supplies")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
            ])
            
            await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await loading_msg.edit_text(
                "😔 Поставки не найдены.\n"
                "Создайте поставку в личном кабинете WB.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data="browser_my_supplies")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error getting supplies: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при загрузке поставок.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повторить", callback_data="browser_my_supplies")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="browser_menu")]
            ])
        )
