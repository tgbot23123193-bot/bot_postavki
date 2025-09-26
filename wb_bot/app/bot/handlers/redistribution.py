"""
Обработчики для функций перераспределения остатков.

Этот модуль содержит все обработчики для автоматизации 
перераспределения остатков товаров на Wildberries.
"""

import asyncio
from typing import Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.callback_data import CallbackData

from ...utils.logger import get_logger
from ...services.database_service import db_service
from ...services.browser_manager import BrowserManager
from ...services.redistribution_service import get_redistribution_service
from ...services.wb_stocks_service import get_wb_stocks_service, WBStocksService
from ..keyboards.inline import get_main_menu
from ..keyboards.inline_redistribution import get_redistribution_menu, create_warehouses_keyboard, RedistributionCallback, WarehouseCallback

logger = get_logger(__name__)
router = Router()


@router.callback_query(F.data == "redistrib_wait_31min")
async def wait_31_minutes_retry(callback: CallbackQuery, state: FSMContext):
    """Обработка ожидания 31 минуты для повтора."""
    try:
        import asyncio
        
        user_id = callback.from_user.id
        state_data = await state.get_data()
        
        await state.set_state(RedistributionStates.waiting_for_retry)
        
        await callback.message.edit_text(
            f"⏳ <b>Ожидание 31 минуты</b>\n\n"
            f"🕐 Бот автоматически повторит попытку\n"
            f"распределения через 31 минуту.\n\n"
            f"📦 Артикул: <code>{state_data.get('article')}</code>\n"
            f"🏪 Откуда: <b>{state_data.get('source_warehouse', {}).get('name')}</b>\n"
            f"📦 Куда: <b>{state_data.get('destination_warehouse', {}).get('name')}</b>\n"
            f"🔢 Количество: <b>{state_data.get('quantity')}</b> шт\n\n"
            f"⚠️ Не закрывайте браузер!\n"
            f"📱 Вы можете свернуть Telegram.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отменить ожидание",
                        callback_data="redistribution_menu"
                    )
                ]
            ])
        )
        
        await callback.answer()
        
        # Ждем 31 минуту
        await asyncio.sleep(31 * 60)
        
        # Проверяем, не отменил ли пользователь
        current_state = await state.get_state()
        if current_state != RedistributionStates.waiting_for_retry.state:
            return
        
        # Пробуем снова весь процесс
        await callback.message.edit_text(
            f"🔄 <b>Повторная попытка распределения</b>\n\n"
            f"⏳ Запускаем процесс заново...",
            parse_mode="HTML"
        )
        
        # Запускаем процесс распределения заново
        redistribution_service = get_redistribution_service(browser_manager)
        
        # Переоткрываем форму
        await redistribution_service.close_and_reopen_redistribution(
            user_id, 
            state_data.get('article')
        )
        
        # Выбираем склад откуда
        await redistribution_service.select_warehouse(
            user_id,
            state_data.get('source_warehouse')
        )
        
        # Выбираем склад куда  
        await redistribution_service.select_destination_warehouse(
            user_id,
            state_data.get('destination_warehouse')
        )
        
        # Вводим количество
        input_result = await redistribution_service.input_quantity(
            user_id, 
            state_data.get('quantity')
        )
        
        # Обрабатываем результат
        if input_result["success"]:
            await callback.message.edit_text(
                f"✅ <b>Перераспределение выполнено!</b>\n\n"
                f"Процесс успешно завершен после повтора.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
        else:
            await callback.message.edit_text(
                f"❌ <b>Повторная попытка не удалась</b>\n\n"
                f"Ошибка: {input_result.get('error')}\n\n"
                f"Попробуйте позже вручную.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при ожидании 31 минуты: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при повторной попытке.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await state.clear()


@router.callback_query(F.data == "redistrib_wait_window")
async def wait_for_time_window(callback: CallbackQuery, state: FSMContext):
    """Обработка ожидания временного окна."""
    try:
        from ...utils.time_utils import get_minutes_until_next_window
        import asyncio
        
        user_id = callback.from_user.id
        minutes_wait = get_minutes_until_next_window()
        
        await state.set_state(RedistributionStates.waiting_for_retry)
        
        await callback.message.edit_text(
            f"⏳ <b>Ожидание временного окна</b>\n\n"
            f"🕐 Бот автоматически начнет процесс распределения\n"
            f"через {minutes_wait} минут, когда откроется окно.\n\n"
            f"⚠️ Не закрывайте браузер!\n"
            f"📱 Вы можете закрыть Telegram, бот продолжит работу.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отменить ожидание",
                        callback_data="redistribution_menu"
                    )
                ]
            ])
        )
        
        await callback.answer()
        
        # Ждем нужное время
        await asyncio.sleep(minutes_wait * 60)
        
        # Проверяем, не отменил ли пользователь
        current_state = await state.get_state()
        if current_state != RedistributionStates.waiting_for_retry.state:
            return
        
        # Начинаем процесс заново
        await state.clear()
        await request_article_input(callback, state)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при ожидании временного окна: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при ожидании временного окна.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await state.clear()


async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """Безопасный вызов callback.answer с обработкой timeout."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except Exception as e:
        logger.debug(f"Не удалось отправить callback answer '{text}': {e}")


# Глобальный браузер менеджер (будет инициализирован в main.py)
browser_manager: Optional[BrowserManager] = None

def init_redistribution_handlers(bm: BrowserManager):
    """Инициализация обработчиков с браузер менеджером."""
    global browser_manager
    browser_manager = bm


class RedistributionStates(StatesGroup):
    """Состояния для процесса перераспределения."""
    waiting_for_article = State()  # Ожидание ввода артикула товара
    waiting_for_source_warehouse = State()  # Ожидание выбора склада откуда забрать
    waiting_for_destination_warehouse = State()  # Ожидание выбора склада назначения (куда)
    waiting_for_quantity = State()  # Ожидание ввода количества для перемещения
    processing_redistribution = State()  # Обработка распределения (бесконечная охота)
    waiting_for_retry = State()  # Ожидание повтора через 31 минуту


# Callback классы импортированы из keyboards.inline_redistribution

class DestinationCallback(CallbackData, prefix="destination"):
    """Callback data for destination warehouse selection."""
    action: str  # select, retry
    warehouse_id: str  # ID склада назначения для выбора
    

# Функция create_warehouses_keyboard импортирована из keyboards.inline_redistribution

def create_destination_keyboard(warehouses: list, show_retry: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками складов назначения."""
    keyboard = []
    
    # Добавляем кнопки складов назначения (по 1 в ряд для удобности)
    for warehouse in warehouses:
        warehouse_button = InlineKeyboardButton(
            text=f"📦 {warehouse['name']}",
            callback_data=DestinationCallback(
                action="select",
                warehouse_id=warehouse['id']
            ).pack()
        )
        keyboard.append([warehouse_button])
    
    # Кнопка повторного получения списка (если была ошибка)
    if show_retry:
        retry_button = InlineKeyboardButton(
            text="🔄 Обновить список",
            callback_data=DestinationCallback(
                action="retry",
                warehouse_id="none"
            ).pack()
        )
        keyboard.append([retry_button])
    
    # Кнопка отмены
    cancel_button = InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="redistribution_menu"
    )
    keyboard.append([cancel_button])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_redistribution_menu() -> InlineKeyboardMarkup:
    """Получить меню перераспределения остатков."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🚀 Открыть страницу перераспределения",
                callback_data=RedistributionCallback(action="start").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="📖 Инструкция",
                callback_data=RedistributionCallback(action="help").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="back_to_main"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_redistribution_progress_menu() -> InlineKeyboardMarkup:
    """Меню во время процесса перераспределения."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=RedistributionCallback(action="cancel").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", 
                callback_data="back_to_main"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "redistribution_menu")
async def show_redistribution_menu(callback: CallbackQuery):
    """Показать меню перераспределения остатков."""
    try:
        user_id = callback.from_user.id
        logger.info(f"👤 Пользователь {user_id} открыл меню перераспределения")
        
        # Проверяем есть ли у пользователя валидная браузерная сессия из таблицы browser_sessions
        browser_session = await db_service.get_browser_session(user_id)
        
        if not browser_session:
            await callback.message.edit_text(
                "❌ <b>Браузерная сессия не найдена</b>\n\n"
                "Для использования функции перераспределения необходимо:\n"
                "1. Добавить API ключ\n"
                "2. Пройти авторизацию в браузере\n\n"
                "💡 Воспользуйтесь функцией 'Мониторинг слотов' для настройки браузера",
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return
        
        if not browser_session.session_valid:
            await callback.message.edit_text(
                "❌ <b>Сессия браузера недействительна</b>\n\n"
                "Ваша браузерная сессия устарела или повреждена.\n"
                "Необходимо заново авторизоваться в WB.\n\n"
                "💡 Воспользуйтесь функцией 'Мониторинг слотов' для повторной авторизации",
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return
        
        if not browser_session.wb_login_success:
            await callback.message.edit_text(
                "⚠️ <b>Авторизация в WB не подтверждена</b>\n\n"
                "Для использования функции перераспределения необходимо:\n"
                "• Успешно авторизоваться в Wildberries через браузер\n"
                "• Подтвердить доступ к личному кабинету\n\n"
                "💡 Запустите мониторинг слотов для завершения авторизации",
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return
        
        # Все проверки пройдены - показываем меню
        last_login = browser_session.last_successful_login
        login_info = f"Последняя авторизация: {last_login.strftime('%d.%m.%Y %H:%M')}" if last_login else "Данные авторизации отсутствуют"
        
        menu_text = (
            "🔄 <b>Перераспределение остатков</b>\n\n"
            "Автоматизация работы со страницей:\n"
            "📋 Отчет по остаткам на складе\n\n"
            f"✅ Браузерная сессия активна\n"
            f"✅ Авторизация в WB подтверждена\n"
            f"📅 {login_info}\n\n"
            "Выберите действие:"
        )
        
        await callback.message.edit_text(
            menu_text,
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при показе меню перераспределения: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(RedistributionCallback.filter(F.action == "start"))
async def request_article_input(callback: CallbackQuery, state: FSMContext):
    """Запрос артикула товара перед началом перераспределения."""
    try:
        user_id = callback.from_user.id
        logger.info(f"👤 Пользователь {user_id} запросил перераспределение - запрашиваем артикул")
        
        # БЕЗ ОГРАНИЧЕНИЙ ПО ВРЕМЕНИ - работаем всегда!
        
        # Переводим пользователя в состояние ожидания артикула
        await state.set_state(RedistributionStates.waiting_for_article)
        
        # Клавиатура для отмены
        cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="redistribution_menu"
                )
            ]
        ])
        
        await callback.message.edit_text(
            "📦 <b>Введите артикул товара</b>\n\n"
            "🔤 Введите артикул товара WB для перераспределения.\n"
            "Например: <code>123456789</code>\n\n"
            "❗ Убедитесь, что артикул введен корректно:\n"
            "• Только цифры\n"
            "• Обычно 8-10 цифр\n"
            "• Без пробелов и символов",
            parse_mode="HTML",
            reply_markup=cancel_keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе артикула: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Не удалось инициализировать процесс перераспределения.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(RedistributionStates.waiting_for_article)
async def process_article_input(message: Message, state: FSMContext):
    """Обработка введенного артикула и запуск перераспределения."""
    try:
        user_id = message.from_user.id
        article = message.text.strip()
        
        logger.info(f"👤 Пользователь {user_id} ввел артикул: {article}")
        
        # Валидация артикула
        if not article.isdigit():
            await message.answer(
                "❌ <b>Неверный формат артикула</b>\n\n"
                "Артикул должен содержать только цифры.\n"
                "Попробуйте еще раз:",
                parse_mode="HTML"
            )
            return
        
        if len(article) < 6 or len(article) > 15:
            await message.answer(
                "❌ <b>Неверная длина артикула</b>\n\n"
                "Артикул должен содержать от 6 до 15 цифр.\n"
                "Попробуйте еще раз:",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем артикул в состоянии
        await state.update_data(article=article)
        
        # Получаем склады через API ДО запуска браузера
        status_message = await message.answer(
            f"🔄 <b>Шаг 2 из 4: Получение складов</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n\n"
            f"⏳ Загружаю склады через WB API...",
            parse_mode="HTML"
        )
        
        # Получаем склады через WB API
        try:
            wb_stocks_service = WBStocksService()
            stocks_result = await wb_stocks_service.get_user_stocks(user_id, article)
            
            if not stocks_result["success"]:
                await status_message.edit_text(
                    f"❌ <b>Ошибка получения данных</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n\n"
                    f"❌ {stocks_result.get('error', 'Неизвестная ошибка')}\n\n"
                    f"💡 Проверьте API ключ в настройках.",
                    parse_mode="HTML",
                    reply_markup=get_redistribution_menu()
                )
                await state.clear()
                return
            
            warehouses = stocks_result.get("warehouses", [])
            if not warehouses:
                await status_message.edit_text(
                    f"📦 <b>Товар не найден на складах</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n\n"
                    f"❌ Товар отсутствует на ваших складах или нет остатков.\n\n"
                    f"💡 Проверьте артикул и наличие товара.",
                    parse_mode="HTML",
                    reply_markup=get_redistribution_menu()
                )
                await state.clear()
                return
            
            # Сохраняем склады в состоянии
            await state.update_data(available_warehouses=warehouses)
            
            # Переходим к выбору склада откуда
            await state.set_state(RedistributionStates.waiting_for_source_warehouse)
            
            # Создаем клавиатуру с доступными складами
            source_keyboard = create_warehouses_keyboard(warehouses, "source")
            
            total_quantity = sum(w.get('quantity', 0) for w in warehouses)
            full_quantity = sum(w.get('full_quantity', 0) for w in warehouses)
            
            await status_message.edit_text(
                f"🏪 <b>Шаг 2 из 4: Выберите склад ОТКУДА забрать</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"📊 Найдено складов: <b>{len(warehouses)}</b>\n"
                f"📦 Доступно к перемещению: <b>{total_quantity}</b> шт\n"
                f"📋 Общий остаток: <b>{full_quantity}</b> шт\n\n"
                f"👇 Выберите склад откуда хотите забрать товар:",
                parse_mode="HTML",
                reply_markup=source_keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении складов: {e}")
            await status_message.edit_text(
                f"❌ <b>Ошибка получения складов</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n\n"
                f"❌ {str(e)}\n\n"
                f"💡 Попробуйте еще раз позже.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
            await state.clear()
            return
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке артикула: {e}")
        await message.answer(
            f"❌ <b>Произошла ошибка</b>\n\n"
            f"Не удалось обработать артикул.\n"
            f"Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        # Очищаем состояние при ошибке
        await state.clear()


@router.callback_query(WarehouseCallback.filter(F.action == "select"))
async def handle_warehouse_selection(callback: CallbackQuery, callback_data: WarehouseCallback, state: FSMContext):
    """Обработка выбора склада пользователем."""
    try:
        user_id = callback.from_user.id
        warehouse_id = callback_data.warehouse_id
        
        logger.info(f"👤 Пользователь {user_id} выбрал склад: {warehouse_id}")
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        warehouses = state_data.get('warehouses', [])
        
        # Находим выбранный склад
        selected_warehouse = None
        for warehouse in warehouses:
            if warehouse['id'] == warehouse_id:
                selected_warehouse = warehouse
                break
        
        if not selected_warehouse:
            await callback.message.edit_text(
                "❌ <b>Ошибка выбора склада</b>\n\n"
                "Выбранный склад не найден в списке.\n"
                "Попробуйте еще раз.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
            await callback.answer("❌ Склад не найден", show_alert=True)
            await state.clear()
            return
        
        if not browser_manager:
            await callback.message.edit_text(
                "❌ <b>Ошибка системы</b>\n\n"
                "Браузер менеджер не инициализирован.",
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )
            await callback.answer("❌ Системная ошибка", show_alert=True)
            await state.clear()
            return
        
        # Показываем процесс выбора склада
        await callback.message.edit_text(
            f"🎯 <b>Выбираем склад</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"🏪 Склад: <b>{selected_warehouse['name']}</b>\n\n"
            f"⏳ Кликаем по складу в браузере...",
            parse_mode="HTML"
        )
        
        # Получаем сервис и выбираем склад (включаем отладку)
        redistribution_service = get_redistribution_service(browser_manager, fast_mode=False)
        result = await redistribution_service.select_warehouse(user_id, selected_warehouse)
        
        logger.info(f"🎯 РЕЗУЛЬТАТ ВЫБОРА СКЛАДА: {result}")
        
        if result.get("warehouse_not_in_list"):
            # Склад не найден в выпадающем списке на сайте
            await callback.message.edit_text(
                f"⚠️ <b>Склад не найден на сайте WB</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Склад: <b>{selected_warehouse['name']}</b>\n\n"
                f"❌ В выпадающем списке нету склада который вы выбрали.\n"
                f"Это может означать, что склад временно недоступен для распределения.\n\n"
                f"⏳ Пробуем другой способ...",
                parse_mode="HTML"
            )
            
            # Закрываем и переоткрываем форму
            reopen_result = await redistribution_service.close_and_reopen_redistribution(user_id, article)
            
            if reopen_result["success"]:
                await callback.message.edit_text(
                    f"🔄 <b>Форма переоткрыта</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n\n"
                    f"❌ К сожалению, склад '{selected_warehouse['name']}' временно недоступен.\n"
                    f"Попробуйте выбрать другой склад из списка.",
                    parse_mode="HTML",
                    reply_markup=create_warehouses_keyboard(warehouses, "source")
                )
            else:
                await callback.message.edit_text(
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Не удалось переоткрыть форму распределения.\n"
                    f"Попробуйте начать заново.",
                    parse_mode="HTML",
                    reply_markup=get_redistribution_menu()
                )
            
            await safe_callback_answer(callback, "⚠️ Склад недоступен")
            return
            
        elif result["success"]:
            # Склад "откуда" выбран успешно, теперь получаем список складов "куда"
            await callback.message.edit_text(
                f"✅ <b>Склад выбран успешно!</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Склад (откуда): <b>{selected_warehouse['name']}</b>\n\n"
                f"⏳ Получаем список складов назначения...",
                parse_mode="HTML"
            )
            
            # Используем фиксированный список складов для назначения
            destination_warehouses = [
                {"id": "dest_1", "name": "Коледино"},
                {"id": "dest_2", "name": "Казань"},
                {"id": "dest_3", "name": "Электросталь"},
                {"id": "dest_4", "name": "Санкт-Петербург Уткина Завод"},
                {"id": "dest_5", "name": "Екатеринбург – Испытателей 14г"},
                {"id": "dest_6", "name": "Тула"},
                {"id": "dest_7", "name": "Невинномысск"},
                {"id": "dest_8", "name": "Рязань (Тюшевское)"},
                {"id": "dest_9", "name": "Котовск"},
                {"id": "dest_10", "name": "Волгоград"},
                {"id": "dest_11", "name": "Сарапул"}
            ]
            
            # Фильтруем - убираем склад откуда
            destination_warehouses = [
                w for w in destination_warehouses 
                if w["name"] != selected_warehouse["name"]
            ]
            
            # Сохраняем данные в состоянии для выбора назначения
            await state.set_state(RedistributionStates.waiting_for_destination)
            await state.update_data(
                article=article,
                source_warehouse=selected_warehouse,
                destination_warehouses=destination_warehouses
            )
            
            # Создаем клавиатуру со складами назначения
            destination_keyboard = create_destination_keyboard(destination_warehouses)
            
            await callback.message.edit_text(
                f"📦 <b>Выберите склад назначения</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{selected_warehouse['name']}</b>\n"
                f"🔢 Доступно складов: {len(destination_warehouses)}\n\n"
                f"👇 Выберите склад назначения из списка ниже:",
                parse_mode="HTML",
                reply_markup=destination_keyboard
            )
            # Безопасный ответ на callback (может быть таймаут)
            await safe_callback_answer(callback, "✅ Выберите склад назначения")
        else:
            # Проверяем, есть ли ошибка выбора склада с возможностью повтора
            if result.get("error") == "warehouse_selection_error" and result.get("need_retry"):
                # Ошибка выбора склада - показываем ошибки и предлагаем выбрать заново
                error_messages = result.get("error_messages", [])
                
                # Формируем читаемый текст ошибок
                if error_messages:
                    if len(error_messages) == 1:
                        # Одна ошибка - показываем без маркеров
                        error_display = f"❌ {error_messages[0]}"
                    else:
                        # Несколько ошибок - показываем списком
                        error_display = "❌ <b>Найдены ошибки:</b>\n" + "\n".join([f"• {msg}" for msg in error_messages])
                else:
                    error_display = "❌ Не удалось выбрать склад (неизвестная ошибка)"
                
                # Создаем клавиатуру с повторным списком складов
                warehouse_keyboard = create_warehouses_keyboard(warehouses, "source")
                
                await callback.message.edit_text(
                    f"⚠️ <b>Ошибка выбора склада</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n"
                    f"🏪 Выбранный склад: <b>{selected_warehouse['name']}</b>\n\n"
                    f"{error_display}\n\n"
                    f"👇 Пожалуйста, выберите другой склад из списка ниже:",
                    parse_mode="HTML",
                    reply_markup=warehouse_keyboard
                )
                await safe_callback_answer(callback, "⚠️ Выберите другой склад", show_alert=True)
            else:
                # Обычная ошибка выбора склада
                error_message = result.get('error', 'Неизвестная ошибка')
                
                # Делаем сообщение об ошибке более читаемым
                if error_message and isinstance(error_message, str):
                    if len(error_message) > 100:
                        # Слишком длинное техническое сообщение - сокращаем
                        display_error = error_message[:100] + "..."
                    else:
                        display_error = error_message
                else:
                    display_error = "Не удалось выбрать склад"
                
                await callback.message.edit_text(
                    f"⚠️ <b>Проблема при выборе склада</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n"
                    f"🏪 Склад: <b>{selected_warehouse['name']}</b>\n\n"
                    f"❌ {display_error}\n\n"
                    f"💡 Попробуйте выбрать склад вручную в браузере.",
                    parse_mode="HTML",
                    reply_markup=get_redistribution_menu()
                )
                await safe_callback_answer(callback, "⚠️ Ошибка выбора склада", show_alert=True)
                await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке выбора склада: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Не удалось обработать выбор склада.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()


@router.callback_query(RedistributionCallback.filter(F.action == "help"))
async def show_redistribution_help(callback: CallbackQuery, callback_data: RedistributionCallback):
    """Показать инструкцию по перераспределению."""
    help_text = (
        "📖 <b>Инструкция: Перераспределение остатков</b>\n\n"
        
        "🎯 <b>Что делает функция:</b>\n"
        "• Автоматически открывает страницу 'Отчет по остаткам на складе'\n"
        "• Находит и нажимает кнопку 'Перераспределить остатки'\n"
        "• Открывает меню для работы с перераспределением\n\n"
        
        "🔧 <b>Требования:</b>\n"
        "✅ Настроенный API ключ\n"
        "✅ Активная авторизация в WB через браузер\n"
        "✅ Доступ к личному кабинету поставщика\n\n"
        
        "📋 <b>Как использовать:</b>\n"
        "1. Нажмите 'Открыть страницу перераспределения'\n"
        "2. Дождитесь загрузки страницы в браузере\n"
        "3. Работайте с открывшимся меню перераспределения\n\n"
        
        "⚠️ <b>Важно:</b>\n"
        "• Не закрывайте браузер во время работы\n"
        "• Убедитесь что авторизация в WB не истекла\n"
        "• При ошибках попробуйте заново авторизоваться"
    )
    
    await callback.message.edit_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_redistribution_menu()
    )
    await callback.answer()


@router.callback_query(DestinationCallback.filter(F.action == "select"))
async def handle_destination_selection(callback: CallbackQuery, callback_data: DestinationCallback, state: FSMContext):
    """Обработка выбора склада назначения."""
    try:
        user_id = callback.from_user.id
        destination_warehouse_id = callback_data.warehouse_id
        
        logger.info(f"👤 Пользователь {user_id} выбрал склад назначения: {destination_warehouse_id}")
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        source_warehouse = state_data.get('source_warehouse')
        destination_warehouses = state_data.get('destination_warehouses', [])
        
        # Находим выбранный склад назначения
        selected_destination = None
        for warehouse in destination_warehouses:
            if warehouse['id'] == destination_warehouse_id:
                selected_destination = warehouse
                break
        
        if not selected_destination:
            await callback.message.edit_text(
                "❌ <b>Ошибка выбора склада назначения</b>\n\n"
                "Выбранный склад не найден в списке.\n"
                "Попробуйте еще раз.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
            await callback.answer("❌ Склад не найден", show_alert=True)
            await state.clear()
            return
        
        # Показываем процесс выбора склада назначения
        await callback.message.edit_text(
            f"🎯 <b>Выбираем склад назначения</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
            f"📦 Куда: <b>{selected_destination['name']}</b>\n\n"
            f"⏳ Кликаем по складу назначения в браузере...",
            parse_mode="HTML"
        )
        
        # Получаем сервис и выбираем склад назначения
        redistribution_service = get_redistribution_service(browser_manager)
        result = await redistribution_service.select_destination_warehouse(user_id, selected_destination)
        
        if result["success"]:
            # Склад назначения выбран успешно, теперь получаем количество товара
            await callback.message.edit_text(
                f"✅ <b>Склад назначения выбран!</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                f"📦 Куда: <b>{selected_destination['name']}</b>\n\n"
                f"⏳ Получаем информацию о количестве товара...",
                parse_mode="HTML"
            )
            
            # Получаем количество товара
            quantity_result = await redistribution_service.get_available_quantity(user_id)
            
            if quantity_result["success"]:
                quantity_text = quantity_result["quantity_text"]
                quantity_number = quantity_result.get("quantity_number")
                
                # Сохраняем данные в состоянии для ввода количества
                await state.set_state(RedistributionStates.waiting_for_quantity)
                await state.update_data(
                    article=article,
                    source_warehouse=source_warehouse,
                    destination_warehouse=selected_destination,
                    available_quantity=quantity_number,
                    quantity_text=quantity_text
                )
                
                # Клавиатура для отмены
                cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❌ Отмена",
                            callback_data="redistribution_menu"
                        )
                    ]
                ])
                
                # Формируем сообщение с количеством
                quantity_message = (
                    f"📊 <b>Информация о товаре</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n"
                    f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                    f"📦 Куда: <b>{selected_destination['name']}</b>\n\n"
                    f"📊 <b>Доступно:</b> {quantity_text}\n\n"
                    f"🔢 <b>Какое количество хотите переместить?</b>\n\n"
                    f"💡 Введите число (например: <code>10</code>):"
                )
                
                if quantity_number:
                    quantity_message += f"\n📝 Максимум: <code>{quantity_number}</code> шт"
                
                await callback.message.edit_text(
                    quantity_message,
                    parse_mode="HTML",
                    reply_markup=cancel_keyboard
                )
                await safe_callback_answer(callback, "✅ Введите количество")
            else:
                await callback.message.edit_text(
                    f"⚠️ <b>Проблема с получением количества</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n"
                    f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                    f"📦 Куда: <b>{selected_destination['name']}</b>\n\n"
                    f"❌ Ошибка: {quantity_result['error']}\n\n"
                    f"💡 Попробуйте завершить настройку вручную в браузере.",
                    parse_mode="HTML",
                    reply_markup=get_redistribution_menu()
                )
                await safe_callback_answer(callback, "⚠️ Ошибка получения количества", show_alert=True)
                await state.clear()
        
        elif result.get("need_retry"):
            # Обработка ошибок с возможностью повторного выбора
            error_messages = result.get("error_messages", [result.get("error", "Неизвестная ошибка")])
            error_text = "\n".join(f"• {msg}" for msg in error_messages)
            
            # Показываем список складов снова для повторного выбора
            destination_keyboard = create_destination_keyboard(destination_warehouses, show_retry=True)
            
            await callback.message.edit_text(
                f"⚠️ <b>Ошибка при выборе склада назначения</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                f"📦 Куда: <b>{selected_destination['name']}</b>\n\n"
                f"🚨 <b>Ошибки:</b>\n{error_text}\n\n"
                f"📸 Скриншот: {result.get('screenshot', 'Не создан')}\n\n"
                f"💡 Выберите другой склад назначения или обновите список:",
                parse_mode="HTML",
                reply_markup=destination_keyboard
            )
            await callback.answer("⚠️ Попробуйте другой склад", show_alert=True)
        
        else:
            await callback.message.edit_text(
                f"⚠️ <b>Проблема при выборе склада назначения</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                f"📦 Куда: <b>{selected_destination['name']}</b>\n"
                f"❌ Ошибка: {result['error']}\n\n"
                f"💡 Попробуйте выбрать склад назначения вручную в браузере.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
            await callback.answer("⚠️ Ошибка выбора склада", show_alert=True)
            await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке выбора склада назначения: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при выборе склада назначения.\n"
            "Попробуйте еще раз.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()


@router.callback_query(DestinationCallback.filter(F.action == "retry"))
async def retry_destination_warehouses(callback: CallbackQuery, callback_data: DestinationCallback, state: FSMContext):
    """Повторное получение списка складов назначения."""
    try:
        user_id = callback.from_user.id
        logger.info(f"👤 Пользователь {user_id} запросил обновление списка складов назначения")
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        source_warehouse = state_data.get('source_warehouse')
        
        await callback.message.edit_text(
            f"🔄 <b>Обновляем список складов назначения</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n\n"
            f"⏳ Получаем актуальный список складов...",
            parse_mode="HTML"
        )
        
        # Получаем обновленный список складов назначения
        redistribution_service = get_redistribution_service(browser_manager)
        destination_result = await redistribution_service.get_destination_warehouses(user_id)
        
        if destination_result["success"]:
            destination_warehouses = destination_result["warehouses"]
            
            # Обновляем данные в состоянии
            await state.update_data(destination_warehouses=destination_warehouses)
            
            # Создаем обновленную клавиатуру
            destination_keyboard = create_destination_keyboard(destination_warehouses)
            
            await callback.message.edit_text(
                f"🔄 <b>Список складов обновлен</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                f"🔢 Доступно складов: {len(destination_warehouses)}\n\n"
                f"👇 Выберите склад назначения из обновленного списка:",
                parse_mode="HTML",
                reply_markup=destination_keyboard
            )
            await callback.answer("✅ Список обновлен")
        else:
            await callback.message.edit_text(
                f"⚠️ <b>Ошибка обновления списка</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                f"❌ Ошибка: {destination_result['error']}\n\n"
                f"💡 Попробуйте выбрать склад назначения вручную в браузере.",
                parse_mode="HTML",
                reply_markup=get_redistribution_menu()
            )
            await callback.answer("⚠️ Ошибка обновления", show_alert=True)
            await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении списка складов назначения: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при обновлении списка складов.\n"
            "Попробуйте еще раз.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()


async def start_redistribution_cycle(message: Message, state: FSMContext):
    """Запускает цикл попыток распределения в заданные периоды."""
    try:
        import asyncio
        from ...utils.redistribution_config import RedistributionConfig
        
        user_id = message.from_user.id
        state_data = await state.get_data()
        
        article = state_data.get('article')
        source_warehouse = state_data.get('source_warehouse')
        destination_warehouse = state_data.get('destination_warehouse')
        quantity = state_data.get('quantity')
        
        # Показываем сообщение о начале процесса
        status_message = await message.answer(
            f"🚀 <b>Запускаем охоту за поставкой!</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
            f"📦 Куда: <b>{destination_warehouse['name']}</b>\n"
            f"🔢 Количество: <b>{quantity}</b> шт\n\n"
            f"⏰ Активные периоды: {', '.join([f'{s.hour:02d}:{s.minute:02d}-{e.hour:02d}:{e.minute:02d}' for s, e in RedistributionConfig.get_booking_periods()])} МСК\n"
            f"🔥 В активные периоды: каждую <b>{RedistributionConfig.get_active_retry_minutes()} минуту</b>\n"
            f"⏳ Вне периодов: каждые <b>{RedistributionConfig.get_retry_minutes()} минут</b>\n"
            f"🔄 Максимум попыток: {RedistributionConfig.get_max_attempts()}\n\n"
            f"🎯 Бот будет <b>умно</b> пытаться поймать поставку!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Остановить охоту",
                        callback_data="redistribution_stop"
                    )
                ]
            ])
        )
        
        await state.set_state(RedistributionStates.processing_redistribution)
        
        attempts = 0
        max_attempts = RedistributionConfig.get_max_attempts()
        
        redistribution_service = get_redistribution_service(browser_manager, fast_mode=True)
        
        while attempts < max_attempts:
            # Проверяем, не отменил ли пользователь
            current_state = await state.get_state()
            if current_state != RedistributionStates.processing_redistribution.state:
                break
            
            attempts += 1
            
            # Определяем текущий интервал и режим
            in_active_period = RedistributionConfig.is_in_booking_period()
            current_retry_interval = RedistributionConfig.get_current_retry_interval()
            
            # Показываем статус с информацией о режиме
            if in_active_period:
                mode_text = f"🔥 <b>АКТИВНЫЙ РЕЖИМ</b> (каждую {current_retry_interval} мин)"
            else:
                mode_text = f"⏳ <b>ОБЫЧНЫЙ РЕЖИМ</b> (каждые {current_retry_interval} мин)"
                minutes_until_active = RedistributionConfig.minutes_until_next_period()
                mode_text += f"\n⏰ До активного периода: {minutes_until_active} мин"
            
            await status_message.edit_text(
                f"🎯 <b>Попытка #{attempts}</b>\n\n"
                f"📦 Артикул: <code>{article}</code>\n"
                f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                f"📦 Куда: <b>{destination_warehouse['name']}</b>\n"
                f"🔢 Количество: <b>{quantity}</b> шт\n\n"
                f"{mode_text}\n\n"
                f"⏳ Пробуем забронировать...",
                parse_mode="HTML"
            )
            
            try:
                # Переоткрываем форму
                await redistribution_service.close_and_reopen_redistribution(user_id, article)
                
                # Выбираем склад откуда
                select_result = await redistribution_service.select_warehouse(user_id, source_warehouse)
                if not select_result["success"]:
                    # Проверяем, нужно ли переоткрыть форму
                    if select_result.get("warehouse_not_in_list"):
                        # Склад отсутствует в списке - это нормально, продолжаем попытки
                        raise Exception(f"📦 Склад '{source_warehouse['name']}' сейчас недоступен в списке WB. Продолжаю поиск...")
                    else:
                        raise Exception(f"Не удалось выбрать склад откуда: {select_result.get('error')}")
                
                # Выбираем склад куда
                dest_result = await redistribution_service.select_destination_warehouse(user_id, destination_warehouse)
                if not dest_result["success"]:
                    if dest_result.get("warehouse_not_in_list"):
                        # Склад назначения отсутствует в списке
                        raise Exception(f"🏭 Склад назначения '{destination_warehouse['name']}' сейчас недоступен. Продолжаю поиск...")
                    else:
                        raise Exception(f"Не удалось выбрать склад куда: {dest_result.get('error')}")
                
                # Вводим количество
                input_result = await redistribution_service.input_quantity(user_id, quantity)
                
                if input_result["success"] and input_result.get("redistribute_clicked"):
                    # УСПЕХ! Закрываем браузер
                    try:
                        logger.info("🎉 Поставка поймана! Закрываем браузер...")
                        await browser_manager.close_browser(user_id)
                        logger.info("✅ Браузер успешно закрыт")
                    except Exception as browser_error:
                        logger.warning(f"⚠️ Не удалось закрыть браузер: {browser_error}")
                    
                    await status_message.edit_text(
                        f"🎉🎉🎉 <b>ПОСТАВКА ПОЙМАНА!</b> 🎉🎉🎉\n\n"
                        f"📦 Артикул: <code>{article}</code>\n"
                        f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
                        f"📦 Куда: <b>{destination_warehouse['name']}</b>\n"
                        f"🔢 Количество: <b>{quantity}</b> шт\n\n"
                        f"✅ <b>ВСЕ УСПЕШНО ЗАБРОНИРОВАНО!</b>\n"
                        f"🎯 Попытка #{attempts} успешна!\n\n"
                        f"😎 Можете кайфовать!",
                        parse_mode="HTML",
                        reply_markup=get_redistribution_menu()
                    )
                    await state.clear()
                    return
                else:
                    raise Exception(input_result.get('error', 'Не удалось забронировать'))
                    
            except Exception as e:
                error_msg = str(e)
                logger.info(f"Попытка #{attempts} не удалась: {error_msg}")
                
                # Определяем тип ошибки для более понятного сообщения
                if "недоступен в списке WB" in error_msg or "Продолжаю поиск" in error_msg:
                    error_icon = "📦"
                    error_type = "Склад временно недоступен"
                elif "лимит" in error_msg.lower() or "исчерпан" in error_msg.lower():
                    error_icon = "⏰"
                    error_type = "Дневной лимит исчерпан"
                elif "количества не найдено" in error_msg:
                    error_icon = "🔢"
                    error_type = "Проблема с полем количества"
                else:
                    error_icon = "❌"
                    error_type = "Техническая ошибка"
                
                await status_message.edit_text(
                    f"{error_icon} <b>Попытка #{attempts}: {error_type}</b>\n\n"
                    f"📦 Артикул: <code>{article}</code>\n"
                    f"🏪 Ищу: <b>{source_warehouse['name']}</b> → <b>{destination_warehouse['name']}</b>\n"
                    f"🔢 Количество: <b>{quantity}</b> шт\n\n"
                    f"💬 {error_msg}\n\n"
                    f"{mode_text}\n"
                    f"⏳ Следующая попытка через {current_retry_interval} минут...",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="❌ Остановить охоту",
                                callback_data="redistribution_stop"
                            )
                        ]
                    ])
                )
            
            # Ждем перед следующей попыткой (динамический интервал)
            await asyncio.sleep(current_retry_interval * 60)
        
        # Достигнут лимит попыток - закрываем браузер
        try:
            logger.info("⚠️ Достигнут лимит попыток. Закрываем браузер...")
            await browser_manager.close_browser(user_id)
            logger.info("✅ Браузер успешно закрыт при достижении лимита")
        except Exception as browser_error:
            logger.warning(f"⚠️ Не удалось закрыть браузер при лимите: {browser_error}")
        
        await status_message.edit_text(
            f"⚠️ <b>Достигнут лимит попыток</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"📊 Сделано попыток: {attempts}\n\n"
            f"Браузер закрыт.\n"
            f"Попробуйте запустить процесс заново.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"❌ Ошибка в цикле распределения: {e}")
        
        # Закрываем браузер при критической ошибке
        try:
            logger.info("❌ Критическая ошибка. Закрываем браузер...")
            await browser_manager.close_browser(user_id)
            logger.info("✅ Браузер успешно закрыт при ошибке")
        except Exception as browser_error:
            logger.warning(f"⚠️ Не удалось закрыть браузер при ошибке: {browser_error}")
        
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка в процессе охоты за поставкой.\n"
            "Браузер закрыт.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await state.clear()


@router.message(RedistributionStates.waiting_for_quantity)
async def process_quantity_input(message: Message, state: FSMContext):
    """Обработка введенного количества для перемещения."""
    try:
        user_id = message.from_user.id
        quantity_str = message.text.strip()
        
        logger.info(f"👤 Пользователь {user_id} ввел количество: {quantity_str}")
        
        # Валидация количества
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                await message.answer(
                    "❌ <b>Неверное количество</b>\n\n"
                    "Количество должно быть положительным числом.\n"
                    "Попробуйте еще раз:",
                    parse_mode="HTML"
                )
                return
        except ValueError:
            await message.answer(
                "❌ <b>Неверный формат</b>\n\n"
                "Введите число (например: <code>10</code>).\n"
                "Попробуйте еще раз:",
                parse_mode="HTML"
            )
            return
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        source_warehouse = state_data.get('source_warehouse')
        destination_warehouse = state_data.get('destination_warehouse')
        available_quantity = state_data.get('available_quantity')
        quantity_text = state_data.get('quantity_text')
        
        # Проверяем, не превышает ли количество доступное
        if available_quantity and quantity > available_quantity:
            await message.answer(
                f"⚠️ <b>Превышено доступное количество</b>\n\n"
                f"📊 Доступно: <b>{available_quantity}</b> шт\n"
                f"📝 Вы ввели: <b>{quantity}</b> шт\n\n"
                f"💡 Введите количество не больше {available_quantity}:",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем количество и запускаем цикл
        await state.update_data(quantity=quantity)
        
        # Запускаем цикл охоты за поставкой
        await start_redistribution_cycle(message, state)
        
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "💡 Введите количество числом (например: 5):",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка обработки количества для пользователя {message.from_user.id}: {e}")
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при обработке количества.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await state.clear()


@router.callback_query(F.data == "redistribution_stop")
async def stop_redistribution_hunt(callback: CallbackQuery, state: FSMContext):
    """Остановить охоту за поставкой."""
    user_id = callback.from_user.id
    
    # Закрываем браузер при остановке
    try:
        logger.info(f"🛑 Пользователь {user_id} остановил охоту. Закрываем браузер...")
        browser_manager = BrowserManager()
        await browser_manager.close_browser(user_id)
        logger.info("✅ Браузер успешно закрыт при остановке охоты")
    except Exception as browser_error:
        logger.warning(f"⚠️ Не удалось закрыть браузер при остановке: {browser_error}")
    
    await state.clear()
    await callback.message.edit_text(
        "🛑 <b>Охота за поставкой остановлена</b>\n\n"
        "Браузер закрыт.\n"
        "Вы можете запустить новую охоту в любое время.",
        parse_mode="HTML",
        reply_markup=get_redistribution_menu()
    )
    await callback.answer("Охота остановлена")


@router.callback_query(RedistributionCallback.filter(F.action == "cancel"))
async def cancel_redistribution(callback: CallbackQuery, callback_data: RedistributionCallback):
    """Отменить процесс перераспределения."""
    await callback.message.edit_text(
        "❌ <b>Перераспределение остатков отменено</b>\n\n"
        "Вы можете вернуться к этой функции в любое время.",
        parse_mode="HTML",
        reply_markup=get_redistribution_menu()
    )
    await callback.answer("Операция отменена")


@router.callback_query(WarehouseCallback.filter(F.action == "source"))
async def handle_source_warehouse_selection(callback: CallbackQuery, callback_data: WarehouseCallback, state: FSMContext):
    """Обработка выбора склада ОТКУДА забрать товар."""
    try:
        user_id = callback.from_user.id
        warehouse_id = callback_data.warehouse_id
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        available_warehouses = state_data.get('available_warehouses', [])
        
        # Находим выбранный склад
        selected_warehouse = None
        for warehouse in available_warehouses:
            if warehouse.get('id') == warehouse_id:
                selected_warehouse = warehouse
                break
        
        if not selected_warehouse:
            await callback.answer("❌ Склад не найден", show_alert=True)
            return
        
        # Сохраняем выбранный склад
        await state.update_data(source_warehouse=selected_warehouse)
        
        # Переходим к выбору склада назначения
        await state.set_state(RedistributionStates.waiting_for_destination_warehouse)
        
        # Создаем список складов назначения (фиксированный)
        destination_warehouses = [
            {"id": "dest_1", "name": "Коледино"},
            {"id": "dest_2", "name": "Казань"},
            {"id": "dest_3", "name": "Электросталь"},
            {"id": "dest_4", "name": "Санкт-Петербург Уткина Завод"},
            {"id": "dest_5", "name": "Екатеринбург – Испытателей 14г"},
            {"id": "dest_6", "name": "Тула"},
            {"id": "dest_7", "name": "Невинномысск"},
            {"id": "dest_8", "name": "Рязань (Тюшевское)"},
            {"id": "dest_9", "name": "Котовск"},
            {"id": "dest_10", "name": "Волгоград"},
            {"id": "dest_11", "name": "Сарапул"}
        ]
        
        # Убираем склад откуда из списка назначения
        destination_warehouses = [
            w for w in destination_warehouses 
            if w["name"] != selected_warehouse["name"]
        ]
        
        # Создаем клавиатуру для склада назначения
        destination_keyboard = create_warehouses_keyboard(destination_warehouses, "destination")
        
        await callback.message.edit_text(
            f"🏭 <b>Шаг 3 из 4: Выберите склад КУДА отправить</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"🏪 Откуда: <b>{selected_warehouse['name']}</b>\n"
            f"📦 Доступно: <b>{selected_warehouse.get('quantity', 0)}</b> шт\n\n"
            f"👇 Выберите склад назначения:",
            parse_mode="HTML",
            reply_markup=destination_keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе склада откуда: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(WarehouseCallback.filter(F.action == "destination"))
async def handle_destination_warehouse_selection(callback: CallbackQuery, callback_data: WarehouseCallback, state: FSMContext):
    """Обработка выбора склада КУДА отправить товар."""
    try:
        user_id = callback.from_user.id
        warehouse_id = callback_data.warehouse_id
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        source_warehouse = state_data.get('source_warehouse')
        
        # Находим выбранный склад назначения
        destination_warehouses = [
            {"id": "dest_1", "name": "Коледино"},
            {"id": "dest_2", "name": "Казань"},
            {"id": "dest_3", "name": "Электросталь"},
            {"id": "dest_4", "name": "Санкт-Петербург Уткина Завод"},
            {"id": "dest_5", "name": "Екатеринбург – Испытателей 14г"},
            {"id": "dest_6", "name": "Тула"},
            {"id": "dest_7", "name": "Невинномысск"},
            {"id": "dest_8", "name": "Рязань (Тюшевское)"},
            {"id": "dest_9", "name": "Котовск"},
            {"id": "dest_10", "name": "Волгоград"},
            {"id": "dest_11", "name": "Сарапул"}
        ]
        
        selected_destination = None
        for warehouse in destination_warehouses:
            if warehouse.get('id') == warehouse_id:
                selected_destination = warehouse
                break
        
        if not selected_destination:
            await callback.answer("❌ Склад не найден", show_alert=True)
            return
        
        # Сохраняем выбранный склад назначения
        await state.update_data(destination_warehouse=selected_destination)
        
        # Переходим к вводу количества
        await state.set_state(RedistributionStates.waiting_for_quantity)
        
        # Создаем клавиатуру отмены
        cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="redistribution_menu"
                )
            ]
        ])
        
        available_quantity = source_warehouse.get('quantity', 0)
        
        await callback.message.edit_text(
            f"🔢 <b>Шаг 4 из 4: Введите количество</b>\n\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"🏪 Откуда: <b>{source_warehouse['name']}</b>\n"
            f"🏭 Куда: <b>{selected_destination['name']}</b>\n"
            f"📦 Доступно: <b>{available_quantity}</b> шт\n\n"
            f"💡 Введите количество товара для перемещения:\n"
            f"(от 1 до {available_quantity} шт)",
            parse_mode="HTML",
            reply_markup=cancel_keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе склада назначения: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(RedistributionStates.waiting_for_quantity)
async def handle_quantity_input(message: Message, state: FSMContext):
    """Обработка ввода количества и запуск бесконечной охоты."""
    try:
        user_id = message.from_user.id
        quantity_str = message.text.strip()
        
        # Валидация количества
        if not quantity_str.isdigit():
            await message.answer(
                "❌ <b>Неверный формат</b>\n\n"
                "💡 Введите количество числом (например: 5):",
                parse_mode="HTML"
            )
            return
        
        quantity = int(quantity_str)
        if quantity <= 0:
            await message.answer(
                "❌ <b>Неверное количество</b>\n\n"
                "💡 Количество должно быть больше 0:",
                parse_mode="HTML"
            )
            return
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        article = state_data.get('article')
        source_warehouse = state_data.get('source_warehouse')
        destination_warehouse = state_data.get('destination_warehouse')
        available_quantity = source_warehouse.get('quantity', 0)
        
        # Проверяем, не превышает ли количество доступное
        if quantity > available_quantity:
            await message.answer(
                f"❌ <b>Превышено доступное количество</b>\n\n"
                f"📊 Доступно: <b>{available_quantity}</b> шт\n"
                f"📝 Вы ввели: <b>{quantity}</b> шт\n\n"
                f"💡 Введите количество не больше {available_quantity}:",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем количество и запускаем бесконечную охоту
        await state.update_data(quantity=quantity)
        
        # Запускаем бесконечную охоту за поставкой
        await start_redistribution_cycle(message, state)
        
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "💡 Введите количество числом (например: 5):",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка обработки количества для пользователя {user_id}: {e}")
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при обработке количества.",
            parse_mode="HTML",
            reply_markup=get_redistribution_menu()
        )
        await state.clear()
