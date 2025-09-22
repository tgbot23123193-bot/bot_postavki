"""
Сервис автоматического бронирования поставок на WB.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import aiohttp
import json
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Используем PostgreSQL для хранения API ключей


class WBBookingService:
    """Сервис для автоматического бронирования поставок."""
    
    BASE_URL = "https://supplies-api.wildberries.ru"
    
    def __init__(self):
        self.session = None
        self.active_bookings = {}  # user_id: {task_id: booking_task}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def create_preorder(
        self,
        api_key: str,
        warehouse_id: int,
        box_type_id: int,
        quantity: int = 1
    ) -> Optional[Dict]:
        """Создать предварительный заказ на поставку."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Проверяем доступность опций приёмки
        from .wb_real_api import wb_real_api
        
        try:
            async with wb_real_api as service:
                # Сначала проверяем опции приёмки
                options = await service.get_acceptance_options(
                    api_key=api_key,
                    items=[{"quantity": quantity, "barcode": "test"}],  # TODO: реальные баркоды
                    warehouse_id=warehouse_id
                )
                
                if not options or not options.get("result"):
                    logger.error("No acceptance options available")
                    return None
            
            # Создаем заказ через правильный API
            # Согласно документации WB, поставки создаются через другой эндпоинт
            data = {
                "name": f"Автопоставка {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "cabinetId": warehouse_id  # ID склада
            }
            
            async with self.session.post(
                f"{self.BASE_URL}/api/v3/supplies",  # Новый эндпоинт для создания поставок
                headers=headers,
                json=data
            ) as resp:
                if resp.status in [200, 201]:
                    result = await resp.json()
                    logger.info(f"Supply created: {result}")
                    return result
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to create supply: {resp.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error creating supply: {e}")
            return None
    
    async def confirm_preorder(
        self,
        api_key: str,
        preorder_id: int
    ) -> bool:
        """Подтвердить предварительный заказ."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.put(
                f"{self.BASE_URL}/api/v1/preorders/{preorder_id}/confirm",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Preorder {preorder_id} confirmed")
                    return True
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to confirm preorder: {resp.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error confirming preorder: {e}")
            return False
    
    async def book_slot(
        self,
        user_id: int,
        warehouse_id: int,
        warehouse_name: str,
        supply_date: str,
        box_type_id: int,
        box_type_name: str,
        quantity: int = 1
    ) -> Tuple[bool, str]:
        """Забронировать слот."""
        from .database_service import db_service
        
        # Получаем API ключи из базы данных
        api_keys = await db_service.get_decrypted_api_keys(user_id)
        if not api_keys:
            return False, "❌ Нет API ключей"
        
        api_key = api_keys[0]
        
        # Создаем поставку
        supply = await self.create_preorder(
            api_key=api_key,
            warehouse_id=warehouse_id,
            box_type_id=box_type_id,
            quantity=quantity
        )
        
        if not supply:
            return False, "❌ Не удалось создать поставку"
        
        supply_id = supply.get("supplyId") or supply.get("id")
        if not supply_id:
            return False, "❌ Не получен ID поставки"
        
        message = (
            f"✅ <b>Поставка создана!</b>\n\n"
            f"📦 Склад: {warehouse_name}\n"
            f"📅 Целевая дата: {supply_date}\n"
            f"📋 Тип: {box_type_name}\n"
            f"🔢 Количество: {quantity}\n"
            f"🆔 ID поставки: {supply_id}\n\n"
            f"⚠️ <b>Важно:</b> Не забудьте добавить товары в поставку!"
        )
        return True, message
    
    async def book_existing_supply(
        self,
        user_id: int,
        supply_id: int,
        warehouse_id: int,
        supply_date: str
    ) -> Tuple[bool, str]:
        """Забронировать существующую поставку на конкретную дату."""
        from .database_service import db_service
        from .payment_service import payment_service
        
        # Проверяем баланс пользователя (только если платежи включены)
        from ..config import get_settings
        settings = get_settings()
        
        if settings.payment.payment_enabled:
            balance_info = await payment_service.get_user_balance_info(user_id)
            if not balance_info['can_afford_booking']:
                return False, (
                    f"❌ <b>Недостаточно средств</b>\n\n"
                    f"💰 Баланс: {balance_info['balance']:.2f} ₽\n"
                    f"💳 Требуется: 10 ₽\n\n"
                    f"Пополните баланс для бронирования поставок."
                )
        
        # Получаем API ключи из базы данных
        api_keys = await db_service.get_decrypted_api_keys(user_id)
        if not api_keys:
            return False, "❌ Нет API ключей"
        
        api_key = api_keys[0]
        
        # Получаем детали поставки
        from .wb_real_api import wb_real_api
        
        try:
            async with wb_real_api as service:
                supply_details = await service.get_supply_details(api_key, supply_id)
                
                if not supply_details:
                    return False, "❌ Не удалось получить данные поставки"
            
            # Бронируем слот для поставки через API планирования
            headers = {
                "Authorization": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            booking_data = {
                "supplyId": supply_id,
                "warehouseId": warehouse_id,
                "date": supply_date
            }
            
            async with self.session.put(
                f"{self.BASE_URL}/api/v1/supplies/{supply_id}/timetable",
                headers=headers,
                json=booking_data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Списываем средства за успешное бронирование
                    charge_success, charge_error = await payment_service.charge_for_booking(user_id)
                    
                    if charge_success:
                        # Формируем сообщение в зависимости от настроек
                        if settings.payment.payment_enabled:
                            # Получаем обновленный баланс
                            updated_balance = await payment_service.get_user_balance_info(user_id)
                            
                            message = (
                                f"✅ <b>Поставка забронирована!</b>\n\n"
                                f"🆔 ID поставки: {supply_id}\n"
                                f"📦 Склад: {supply_details.get('warehouseName', 'Неизвестен')}\n"
                                f"📅 Дата: {supply_date}\n"
                                f"📋 Статус: {supply_details.get('statusName', 'Запланировано')}\n"
                                f"📞 Телефон: {supply_details.get('phone', 'Не указан')}\n\n"
                                f"💰 Списано: 10 ₽\n"
                                f"💳 Баланс: {updated_balance['balance']:.2f} ₽\n\n"
                                f"🎉 Поставка успешно запланирована!"
                            )
                        else:
                            message = (
                                f"✅ <b>Поставка забронирована!</b>\n\n"
                                f"🆔 ID поставки: {supply_id}\n"
                                f"📦 Склад: {supply_details.get('warehouseName', 'Неизвестен')}\n"
                                f"📅 Дата: {supply_date}\n"
                                f"📋 Статус: {supply_details.get('statusName', 'Запланировано')}\n"
                                f"📞 Телефон: {supply_details.get('phone', 'Не указан')}\n\n"
                                f"🎉 Поставка успешно запланирована!"
                            )
                        return True, message
                    else:
                        # Если не удалось списать средства, отменяем бронирование
                        logger.error(f"Failed to charge user {user_id} for booking: {charge_error}")
                        return False, f"❌ Ошибка списания средств: {charge_error}"
                else:
                    error_text = await resp.text()
                    logger.error(f"Failed to book supply: {resp.status} - {error_text}")
                    return False, f"❌ Ошибка бронирования: {resp.status}"
                    
        except Exception as e:
            logger.error(f"Error booking existing supply: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    async def start_auto_booking(
        self,
        user_id: int,
        task_id: str,
        warehouse_id: int,
        warehouse_name: str,
        supply_type: str,
        target_dates: List[str],
        max_coefficient: int,
        check_interval: int = 30
    ):
        """Запустить автоматическое бронирование."""
        logger.info(f"Starting auto booking for user {user_id}, task {task_id}")
        
        while task_id in self.active_bookings.get(user_id, {}):
            try:
                # Импортируем здесь чтобы избежать циклических импортов
                from .wb_real_api import wb_real_api
                
                async with wb_real_api as service:
                    # Получаем доступные слоты
                    slots = await service.find_available_slots(
                        user_id=user_id,
                        warehouse_id=warehouse_id,
                        supply_type=supply_type,
                        max_coefficient=max_coefficient,
                        days_ahead=30
                    )
                    
                    # Фильтруем по целевым датам
                    for slot in slots:
                        if slot['date'] in target_dates and slot['coefficient'] == 0:
                            # Пытаемся забронировать
                            success, message = await self.book_slot(
                                user_id=user_id,
                                warehouse_id=warehouse_id,
                                warehouse_name=warehouse_name,
                                supply_date=slot['date'],
                                box_type_id=slot.get('boxTypeId', 5),
                                box_type_name=slot.get('boxType', 'Короба'),
                                quantity=1
                            )
                            
                            if success:
                                # Уведомляем пользователя
                                from ..bot.utils.notifications import notify_user
                                await notify_user(user_id, message)
                                
                                # Останавливаем задачу после успешного бронирования
                                self.stop_booking(user_id, task_id)
                                return
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in auto booking task: {e}")
                await asyncio.sleep(check_interval)
    
    def stop_booking(self, user_id: int, task_id: str):
        """Остановить автобронирование."""
        if user_id in self.active_bookings:
            if task_id in self.active_bookings[user_id]:
                task = self.active_bookings[user_id][task_id]
                task.cancel()
                del self.active_bookings[user_id][task_id]
                logger.info(f"Stopped booking task {task_id} for user {user_id}")
    
    def get_active_bookings(self, user_id: int) -> List[str]:
        """Получить список активных задач автобронирования."""
        return list(self.active_bookings.get(user_id, {}).keys())


# Глобальный экземпляр сервиса
booking_service = WBBookingService()
