"""
Payment service for YooKassa integration.

Handles payment creation, status checking, and balance management
with proper error handling and transaction safety.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple, Any

from yookassa import Configuration, Payment as YooKassaPayment
from yookassa.domain.response import PaymentResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database.connection import get_session
from ..database.models import (
    User, UserBalance, Payment, BalanceTransaction,
    PaymentStatus, TransactionType
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PaymentService:
    """Service for handling payments and balance operations."""
    
    def __init__(self):
        """Initialize payment service."""
        self.settings = get_settings()
        self._configure_yookassa()
    
    def _configure_yookassa(self):
        """Configure YooKassa SDK."""
        if self.settings.payment.yookassa_shop_id and self.settings.payment.yookassa_secret_key:
            Configuration.configure(
                account_id=self.settings.payment.yookassa_shop_id,
                secret_key=self.settings.payment.yookassa_secret_key
            )
            logger.info("YooKassa configured successfully")
        else:
            logger.warning("YooKassa credentials not provided")
    
    async def get_or_create_user_balance(self, user_id: int) -> UserBalance:
        """Get or create user balance."""
        async with get_session() as session:
            # Попытка найти существующий баланс
            stmt = select(UserBalance).where(UserBalance.user_id == user_id)
            result = await session.execute(stmt)
            balance = result.scalar_one_or_none()
            
            if balance:
                return balance
            
            # Создаем новый баланс
            balance = UserBalance(user_id=user_id)
            session.add(balance)
            
            try:
                await session.commit()
                await session.refresh(balance)
                logger.info(f"Created new balance for user {user_id}")
                return balance
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating balance for user {user_id}: {e}")
                raise
    
    async def get_user_balance_info(self, user_id: int) -> Dict[str, Any]:
        """Get user balance information."""
        # Если платежи отключены, возвращаем бесконечный баланс
        if not self.settings.payment.payment_enabled:
            return {
                "balance": 999999.0,
                "total_spent": 0.0,
                "total_deposited": 0.0,
                "bookings_count": 0,
                "can_afford_booking": True
            }
        
        try:
            balance = await self.get_or_create_user_balance(user_id)
            
            return {
                "balance": float(balance.balance),
                "total_spent": float(balance.total_spent),
                "total_deposited": float(balance.total_deposited),
                "bookings_count": balance.bookings_count,
                "can_afford_booking": balance.can_afford_booking(self.settings.payment.booking_cost)
            }
        except Exception as e:
            logger.error(f"Error getting balance info for user {user_id}: {e}")
            return {
                "balance": 0.0,
                "total_spent": 0.0,
                "total_deposited": 0.0,
                "bookings_count": 0,
                "can_afford_booking": False
            }
    
    async def create_payment(
        self,
        user_id: int,
        amount: float,
        description: str = "Пополнение баланса"
    ) -> Tuple[bool, Optional[Payment], Optional[str]]:
        """Create a new payment."""
        try:
            # Валидация суммы
            if amount < self.settings.payment.min_deposit_amount:
                return False, None, f"Минимальная сумма пополнения: {self.settings.payment.min_deposit_amount} ₽"
            
            if amount > self.settings.payment.max_deposit_amount:
                return False, None, f"Максимальная сумма пополнения: {self.settings.payment.max_deposit_amount} ₽"
            
            # Создаем платеж в YooKassa
            idempotence_key = str(uuid.uuid4())
            
            payment_data = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": self.settings.payment.currency
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/your_bot"  # Замените на ваш бот
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "bot_payment": "true"
                }
            }
            
            # Добавляем webhook URL если настроен
            if self.settings.payment.webhook_url:
                payment_data["confirmation"]["return_url"] = self.settings.payment.webhook_url
            
            yookassa_payment = YooKassaPayment.create(payment_data, idempotence_key)
            
            # Сохраняем в базу данных
            async with get_session() as session:
                payment = Payment(
                    user_id=user_id,
                    yookassa_payment_id=yookassa_payment.id,
                    amount=amount,
                    currency=self.settings.payment.currency,
                    description=description,
                    status=PaymentStatus.PENDING,
                    confirmation_url=yookassa_payment.confirmation.confirmation_url,
                    payment_metadata=json.dumps(payment_data.get("metadata", {}))
                )
                
                session.add(payment)
                await session.commit()
                await session.refresh(payment)
                
                logger.info(f"Created payment {payment.id} for user {user_id}, amount {amount}")
                return True, payment, None
                
        except Exception as e:
            logger.error(f"Error creating payment for user {user_id}: {e}")
            return False, None, f"Ошибка создания платежа: {str(e)}"
    
    async def check_payment_status(self, payment_id: str) -> Tuple[bool, Optional[PaymentStatus], Optional[str]]:
        """Check payment status in YooKassa."""
        try:
            yookassa_payment = YooKassaPayment.find_one(payment_id)
            
            if yookassa_payment.status == "succeeded":
                return True, PaymentStatus.SUCCEEDED, None
            elif yookassa_payment.status == "canceled":
                return True, PaymentStatus.CANCELED, "Платеж отменен"
            elif yookassa_payment.status == "pending":
                return True, PaymentStatus.PENDING, "Платеж в обработке"
            else:
                return True, PaymentStatus.FAILED, f"Неизвестный статус: {yookassa_payment.status}"
                
        except Exception as e:
            logger.error(f"Error checking payment status {payment_id}: {e}")
            return False, None, f"Ошибка проверки статуса: {str(e)}"
    
    async def process_successful_payment(self, payment_id: str) -> Tuple[bool, Optional[str]]:
        """Process successful payment and update user balance."""
        async with get_session() as session:
            try:
                # Найти платеж в базе данных
                stmt = select(Payment).where(Payment.yookassa_payment_id == payment_id)
                result = await session.execute(stmt)
                payment = result.scalar_one_or_none()
                
                if not payment:
                    return False, f"Payment {payment_id} not found"
                
                if payment.status == PaymentStatus.SUCCEEDED:
                    return True, "Payment already processed"
                
                # Получить или создать баланс пользователя
                balance_stmt = select(UserBalance).where(UserBalance.user_id == payment.user_id)
                balance_result = await session.execute(balance_stmt)
                user_balance = balance_result.scalar_one_or_none()
                
                if not user_balance:
                    user_balance = UserBalance(user_id=payment.user_id)
                    session.add(user_balance)
                    await session.flush()
                
                # Сохранить баланс до изменения
                balance_before = user_balance.balance
                
                # Обновить баланс
                user_balance.balance += payment.amount
                user_balance.total_deposited += payment.amount
                
                # Создать транзакцию
                transaction = BalanceTransaction(
                    user_id=payment.user_id,
                    balance_id=user_balance.id,
                    transaction_type=TransactionType.DEPOSIT,
                    amount=payment.amount,
                    description=f"Пополнение через YooKassa: {payment.amount} ₽",
                    balance_before=balance_before,
                    balance_after=user_balance.balance,
                    payment_id=payment.id
                )
                session.add(transaction)
                
                # Обновить статус платежа
                payment.status = PaymentStatus.SUCCEEDED
                payment.paid_at = datetime.now(timezone.utc)
                
                await session.commit()
                
                logger.info(f"Processed successful payment {payment_id}: user {payment.user_id} +{payment.amount} ₽")
                return True, None
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error processing successful payment {payment_id}: {e}")
                return False, f"Ошибка обработки платежа: {str(e)}"
    
    async def charge_for_booking(self, user_id: int, booking_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Charge user for booking."""
        # Если платежи отключены, всегда возвращаем успех
        if not self.settings.payment.payment_enabled:
            logger.info(f"Payment disabled - skipping charge for user {user_id}")
            return True, None
        
        async with get_session() as session:
            try:
                # Получить баланс пользователя
                stmt = select(UserBalance).where(UserBalance.user_id == user_id)
                result = await session.execute(stmt)
                user_balance = result.scalar_one_or_none()
                
                if not user_balance:
                    return False, "Баланс не найден"
                
                cost = self.settings.payment.booking_cost
                
                if not user_balance.can_afford_booking(cost):
                    return False, f"Недостаточно средств. Требуется: {cost} ₽, доступно: {user_balance.balance} ₽"
                
                # Сохранить баланс до изменения
                balance_before = user_balance.balance
                
                # Списать средства
                if not user_balance.deduct_for_booking(cost):
                    return False, "Не удалось списать средства"
                
                # Создать транзакцию
                transaction = BalanceTransaction(
                    user_id=user_id,
                    balance_id=user_balance.id,
                    transaction_type=TransactionType.WITHDRAWAL,
                    amount=-cost,  # Отрицательная сумма для списания
                    description=f"Оплата бронирования: {cost} ₽",
                    balance_before=balance_before,
                    balance_after=user_balance.balance,
                    booking_id=booking_id
                )
                session.add(transaction)
                
                await session.commit()
                
                logger.info(f"Charged user {user_id} for booking: -{cost} ₽, balance: {user_balance.balance} ₽")
                return True, None
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error charging user {user_id} for booking: {e}")
                return False, f"Ошибка списания средств: {str(e)}"
    
    async def get_user_transactions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user transaction history."""
        try:
            async with get_session() as session:
                stmt = (
                    select(BalanceTransaction)
                    .where(BalanceTransaction.user_id == user_id)
                    .order_by(BalanceTransaction.created_at.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                transactions = result.scalars().all()
                
                return [
                    {
                        "id": t.id,
                        "type": t.transaction_type.value,
                        "amount": t.amount,
                        "description": t.description,
                        "balance_before": t.balance_before,
                        "balance_after": t.balance_after,
                        "created_at": t.created_at.isoformat(),
                        "payment_id": t.payment_id,
                        "booking_id": t.booking_id
                    }
                    for t in transactions
                ]
        except Exception as e:
            logger.error(f"Error getting transactions for user {user_id}: {e}")
            return []
    
    async def get_pending_payments(self, user_id: int) -> List[Payment]:
        """Get user's pending payments."""
        try:
            async with get_session() as session:
                stmt = (
                    select(Payment)
                    .where(
                        Payment.user_id == user_id,
                        Payment.status == PaymentStatus.PENDING
                    )
                    .order_by(Payment.created_at.desc())
                )
                result = await session.execute(stmt)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting pending payments for user {user_id}: {e}")
            return []


# Global service instance
payment_service = PaymentService()
