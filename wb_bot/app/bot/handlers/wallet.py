"""
Wallet and payment handlers for the Telegram bot.

Handles personal cabinet, balance management, payments and transaction history.
"""

import re
from datetime import datetime
from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
)

from ...services.payment_service import payment_service
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Create router
router = Router()


class WalletStates(StatesGroup):
    """States for wallet operations."""
    entering_amount = State()
    confirming_payment = State()


def format_balance_text(balance_info: Dict[str, Any]) -> str:
    """Format balance information text."""
    return (
        f"💰 <b>Ваш баланс: {balance_info['balance']:.2f} ₽</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Всего пополнено: {balance_info['total_deposited']:.2f} ₽\n"
        f"• Всего потрачено: {balance_info['total_spent']:.2f} ₽\n"
        f"• Бронирований: {balance_info['bookings_count']} шт.\n\n"
        f"💡 <b>Тарифы:</b>\n"
        f"• Одно бронирование: 10 ₽\n"
        f"• Минимальное пополнение: 500 ₽\n\n"
        f"{'✅ Достаточно средств для бронирования' if balance_info['can_afford_booking'] else '❌ Недостаточно средств для бронирования'}"
    )


def get_wallet_keyboard() -> InlineKeyboardMarkup:
    """Get wallet main keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="wallet_deposit")],
        [InlineKeyboardButton(text="📋 История операций", callback_data="wallet_history")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="wallet_refresh")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu")]
    ])


def get_deposit_amounts_keyboard() -> InlineKeyboardMarkup:
    """Get deposit amounts keyboard."""
    amounts = [500, 1000, 2000, 5000, 10000]
    buttons = []
    
    # Создаем кнопки с суммами по 2 в ряду
    for i in range(0, len(amounts), 2):
        row = []
        for j in range(2):
            if i + j < len(amounts):
                amount = amounts[i + j]
                row.append(InlineKeyboardButton(
                    text=f"{amount} ₽",
                    callback_data=f"deposit_amount:{amount}"
                ))
        buttons.append(row)
    
    # Добавляем кнопку "Другая сумма"
    buttons.append([InlineKeyboardButton(text="💰 Другая сумма", callback_data="deposit_custom")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("wallet", "balance"))
async def wallet_command(message: Message):
    """Handle wallet command."""
    from ...config import get_settings
    settings = get_settings()
    
    # Если платежи отключены, показываем сообщение
    if not settings.payment.payment_enabled:
        await message.answer(
            "💰 <b>Платежная система отключена</b>\n\n"
            "Все функции бота доступны бесплатно!\n"
            "Бронируйте поставки без ограничений.",
            parse_mode="HTML"
        )
        return
    
    user_id = message.from_user.id
    
    # Показываем индикатор загрузки
    loading_msg = await message.answer("⏳ Загружаю информацию о балансе...")
    
    try:
        # Получаем информацию о балансе
        balance_info = await payment_service.get_user_balance_info(user_id)
        
        text = format_balance_text(balance_info)
        keyboard = get_wallet_keyboard()
        
        await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing wallet for user {user_id}: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка при загрузке информации о балансе. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повторить", callback_data="wallet_main")]
            ])
        )


@router.callback_query(F.data == "wallet_main")
async def wallet_main_callback(callback: CallbackQuery):
    """Handle wallet main callback."""
    from ...config import get_settings
    settings = get_settings()
    
    # Если платежи отключены, показываем сообщение
    if not settings.payment.payment_enabled:
        await callback.message.edit_text(
            "💰 <b>Платежная система отключена</b>\n\n"
            "Все функции бота доступны бесплатно!\n"
            "Бронируйте поставки без ограничений.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    
    try:
        # Получаем информацию о балансе
        balance_info = await payment_service.get_user_balance_info(user_id)
        
        text = format_balance_text(balance_info)
        keyboard = get_wallet_keyboard()
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing wallet for user {user_id}: {e}")
        await callback.answer("Ошибка при загрузке баланса", show_alert=True)


@router.callback_query(F.data == "wallet_refresh")
async def wallet_refresh_callback(callback: CallbackQuery):
    """Handle wallet refresh callback."""
    await callback.answer("🔄 Обновляю...")
    await wallet_main_callback(callback)


@router.callback_query(F.data == "wallet_deposit")
async def wallet_deposit_callback(callback: CallbackQuery):
    """Handle wallet deposit callback."""
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Выберите сумму пополнения или введите свою:\n\n"
        "💡 <b>Минимальная сумма:</b> 500 ₽\n"
        "💡 <b>Максимальная сумма:</b> 50 000 ₽\n\n"
        "⚡ Платежи обрабатываются мгновенно"
    )
    
    keyboard = get_deposit_amounts_keyboard()
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_amount:"))
async def deposit_amount_callback(callback: CallbackQuery, state: FSMContext):
    """Handle deposit amount selection."""
    amount = int(callback.data.split(":")[1])
    await process_deposit_amount(callback, state, amount)


@router.callback_query(F.data == "deposit_custom")
async def deposit_custom_callback(callback: CallbackQuery, state: FSMContext):
    """Handle custom deposit amount."""
    text = (
        "💰 <b>Введите сумму пополнения</b>\n\n"
        "Введите сумму от 500 до 50 000 рублей:\n\n"
        "Например: <code>1000</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_deposit")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(WalletStates.entering_amount)
    await callback.answer()


@router.message(WalletStates.entering_amount)
async def handle_custom_amount(message: Message, state: FSMContext):
    """Handle custom amount input."""
    try:
        # Извлекаем числа из сообщения
        amount_text = re.sub(r'[^\d]', '', message.text)
        if not amount_text:
            await message.answer(
                "❌ Некорректная сумма. Введите число от 500 до 50 000:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_deposit")]
                ])
            )
            return
        
        amount = int(amount_text)
        
        if amount < 500:
            await message.answer(
                "❌ Минимальная сумма пополнения: 500 ₽",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_deposit")]
                ])
            )
            return
        
        if amount > 50000:
            await message.answer(
                "❌ Максимальная сумма пополнения: 50 000 ₽",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_deposit")]
                ])
            )
            return
        
        # Создаем fake callback для процесса оплаты
        class FakeCallback:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
            
            async def answer(self, text="", show_alert=False):
                pass
        
        fake_callback = FakeCallback(message)
        await process_deposit_amount(fake_callback, state, amount)
        
    except ValueError:
        await message.answer(
            "❌ Некорректная сумма. Введите число от 500 до 50 000:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_deposit")]
            ])
        )


async def process_deposit_amount(callback: CallbackQuery, state: FSMContext, amount: int):
    """Process deposit amount and create payment."""
    user_id = callback.from_user.id
    
    # Показываем подтверждение
    text = (
        f"💳 <b>Подтверждение пополнения</b>\n\n"
        f"💰 Сумма: <b>{amount} ₽</b>\n"
        f"💳 Способ оплаты: ЮKassa\n"
        f"⚡ Зачисление: мгновенно\n\n"
        f"Нажмите «Оплатить» для создания ссылки на оплату."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", callback_data=f"confirm_payment:{amount}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_deposit")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data.startswith("confirm_payment:"))
async def confirm_payment_callback(callback: CallbackQuery):
    """Handle payment confirmation."""
    amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Показываем процесс создания платежа
    await callback.message.edit_text(
        "⏳ Создаю ссылку для оплаты...",
        parse_mode="HTML"
    )
    
    try:
        # Создаем платеж
        success, payment, error = await payment_service.create_payment(
            user_id=user_id,
            amount=float(amount),
            description=f"Пополнение баланса бота на {amount} ₽"
        )
        
        if success and payment:
            text = (
                f"💳 <b>Ссылка для оплаты создана</b>\n\n"
                f"💰 Сумма: <b>{amount} ₽</b>\n"
                f"🆔 Платеж: <code>{payment.yookassa_payment_id}</code>\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После оплаты баланс обновится автоматически."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment.confirmation_url)],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment:{payment.yookassa_payment_id}")],
                [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
            ])
            
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            
        else:
            await callback.message.edit_text(
                f"❌ <b>Ошибка создания платежа</b>\n\n{error}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="wallet_deposit")],
                    [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
                ])
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error creating payment for user {user_id}: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании платежа. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
            ])
        )
        await callback.answer()


@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment_callback(callback: CallbackQuery):
    """Handle payment status check."""
    payment_id = callback.data.split(":")[1]
    
    await callback.answer("🔄 Проверяю статус платежа...")
    
    try:
        # Проверяем статус платежа
        success, status, error = await payment_service.check_payment_status(payment_id)
        
        if success and status:
            if status.value == "succeeded":
                # Обрабатываем успешный платеж
                processed, process_error = await payment_service.process_successful_payment(payment_id)
                
                if processed:
                    # Получаем обновленный баланс
                    balance_info = await payment_service.get_user_balance_info(callback.from_user.id)
                    
                    text = (
                        f"✅ <b>Платеж успешно обработан!</b>\n\n"
                        f"💰 Ваш баланс: <b>{balance_info['balance']:.2f} ₽</b>\n\n"
                        f"Спасибо за пополнение!"
                    )
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💰 К балансу", callback_data="wallet_main")],
                        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
                    ])
                    
                    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
                    
                else:
                    await callback.message.edit_text(
                        f"❌ Ошибка обработки платежа: {process_error}",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
                        ])
                    )
                    
            elif status.value == "pending":
                await callback.answer("⏳ Платеж еще в обработке", show_alert=True)
                
            elif status.value == "canceled":
                await callback.message.edit_text(
                    "❌ <b>Платеж отменен</b>\n\nВы можете создать новый платеж.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Новый платеж", callback_data="wallet_deposit")],
                        [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
                    ])
                )
                
            else:
                await callback.answer(f"❌ {error or 'Неизвестная ошибка'}", show_alert=True)
        else:
            await callback.answer(f"❌ {error or 'Ошибка проверки платежа'}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error checking payment {payment_id}: {e}")
        await callback.answer("❌ Ошибка проверки платежа", show_alert=True)


@router.callback_query(F.data == "wallet_history")
async def wallet_history_callback(callback: CallbackQuery):
    """Handle wallet history callback."""
    user_id = callback.from_user.id
    
    await callback.answer("📋 Загружаю историю...")
    
    try:
        # Получаем историю транзакций
        transactions = await payment_service.get_user_transactions(user_id, limit=10)
        
        if not transactions:
            text = (
                "📋 <b>История операций</b>\n\n"
                "У вас пока нет операций.\n\n"
                "💡 Пополните баланс, чтобы начать использовать бота!"
            )
        else:
            text = "📋 <b>История операций</b>\n\n"
            
            for tx in transactions:
                date = datetime.fromisoformat(tx['created_at'].replace('Z', '+00:00'))
                date_str = date.strftime("%d.%m.%Y %H:%M")
                
                if tx['amount'] > 0:
                    emoji = "💰"
                    amount_str = f"+{tx['amount']:.2f} ₽"
                else:
                    emoji = "💸"
                    amount_str = f"{tx['amount']:.2f} ₽"
                
                text += f"{emoji} <b>{amount_str}</b>\n"
                text += f"📝 {tx['description']}\n"
                text += f"📅 {date_str}\n"
                text += f"💰 Баланс: {tx['balance_after']:.2f} ₽\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="wallet_history")],
            [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error showing wallet history for user {user_id}: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке истории операций.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К балансу", callback_data="wallet_main")]
            ])
        )


# Export router
__all__ = ["router"]
