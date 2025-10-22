"""
Клиент для работы с API поставок Wildberries
"""
import asyncio
import aiohttp
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)


class WBSuppliesAPIClient:
    """Клиент для работы с API поставок Wildberries."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://supplies-api.wildberries.ru/api/v1"
        self.session = None
        
    async def __aenter__(self):
        """Создаем aiohttp сессию."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "WB-Supplies-Bot/1.0"
            },
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрываем aiohttp сессию."""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Выполняет HTTP запрос к API."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Логируем параметры запроса для отладки
            if kwargs.get("params"):
                logger.info(f"📡 {method.upper()} запрос: {url}?{kwargs['params']}")
            else:
                logger.info(f"📡 {method.upper()} запрос: {url}")
            
            async with self.session.request(method, url, **kwargs) as response:
                logger.info(f"📊 Ответ API: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Успешный ответ от API WB")
                    return data
                elif response.status == 401:
                    logger.error("❌ Ошибка авторизации: неверный API ключ")
                    raise Exception("Неверный API ключ WB")
                elif response.status == 429:
                    logger.warning("⚠️ Превышен лимит запросов, ждем...")
                    await asyncio.sleep(5)
                    # Повторяем запрос
                    return await self._make_request(method, endpoint, **kwargs)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка API WB: {response.status} - {error_text}")
                    raise Exception(f"Ошибка API WB: {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"❌ Сетевая ошибка: {e}")
            raise Exception(f"Сетевая ошибка: {e}")
    
    def _get_status_name(self, status_id: int) -> str:
        """Возвращает человекочитаемое название статуса поставки."""
        status_map = {
            1: "Не запланировано",
            2: "Запланировано", 
            3: "Отгрузка разрешена",
            4: "Идёт приёмка",
            5: "Принято",
            6: "Отгружено на воротах"
        }
        return status_map.get(status_id, f"Статус {status_id}")
    
    async def get_supplies(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Получает список поставок.
        
        Args:
            limit: Максимальное количество поставок (по умолчанию 1000)
            
        Returns:
            Список поставок
        """
        logger.info(f"📦 Получаю список поставок (лимит: {limit})")
        
        try:
            # JSON тело запроса для получения поставок со статусами 1 и 2
            # Убираем фильтр по датам, так как у статуса 1 (Не запланировано) factDate = null
            request_body = {
                "statusIDs": [1, 2]  # 1 — Не запланировано, 2 — Запланировано
            }
            
            response = await self._make_request(
                "POST", 
                "/supplies",
                json=request_body
            )
            
            # Логируем полный ответ для отладки
            logger.info(f"🔍 Полный ответ от API WB: {response}")
            
            supplies = response.get("supplies", []) if isinstance(response, dict) else response
            logger.info(f"✅ Получено поставок из API: {len(supplies)}")
            
            # Логируем первую поставку для отладки
            if supplies:
                logger.info(f"🔍 Пример поставки из API: {supplies[0]}")
            
            # Форматируем поставки для отображения
            formatted_supplies = []
            for i, supply in enumerate(supplies[:limit]):  # Ограничиваем только количество
                logger.info(f"🔍 Обрабатываю поставку {i+1}: {supply}")
                
                # Используем правильные поля от WB API
                # Для статуса "Не запланировано" supplyID = null, используем preorderID
                supply_id = supply.get("supplyID") or supply.get("preorderID")
                preorder_id = supply.get("preorderID")
                
                # Формируем название поставки
                if supply.get("supplyID"):
                    supply_name = f"Поставка №{supply_id}"
                else:
                    supply_name = f"Заказ №{preorder_id}"
                
                status_name = supply.get("statusName", "Неизвестно")
                create_date = supply.get("createDate", "")
                
                formatted_supply = {
                    "id": supply_id,
                    "name": supply_name,
                    "status": status_name,
                    "statusName": status_name,
                    "createDate": create_date,
                    "supplyDate": supply.get("supplyDate"),
                    "factDate": supply.get("factDate"),
                    "updatedDate": supply.get("updatedDate"),
                    "preorderID": preorder_id,
                    "supplyID": supply.get("supplyID"),
                    "phone": supply.get("phone")
                }
                
                logger.info(f"📦 Форматированная поставка {i+1}: {formatted_supply}")
                formatted_supplies.append(formatted_supply)
            
            logger.info(f"📋 Отформатировано поставок: {len(formatted_supplies)}")
            return formatted_supplies
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения поставок: {e}")
            raise
    
    async def get_warehouses(self) -> List[Dict[str, Any]]:
        """
        Получает список доступных складов.
        
        Returns:
            Список складов
        """
        logger.info("🏬 Получаю список складов")
        
        try:
            response = await self._make_request("GET", "/warehouses")
            
            # API возвращает массив складов напрямую
            if isinstance(response, list):
                warehouses = response
            else:
                warehouses = response.get("warehouses", [])
                
            logger.info(f"✅ Получено складов: {len(warehouses)}")
            logger.info(f"🔍 Пример склада: {warehouses[0] if warehouses else 'Нет данных'}")
            
            # Форматируем данные складов
            formatted_warehouses = []
            for warehouse in warehouses:
                formatted_warehouses.append({
                    "id": warehouse.get("ID") or warehouse.get("id") or warehouse.get("warehouseID"),
                    "name": warehouse.get("name") or warehouse.get("warehouseName"),
                    "address": warehouse.get("address", ""),
                    "workTime": warehouse.get("workTime", ""),
                    "acceptsQR": warehouse.get("acceptsQR", False),
                    "cargoType": warehouse.get("cargoType", 1)
                })
            
            return formatted_warehouses
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения складов: {e}")
            raise
    
    async def get_acceptance_coefficients(self, warehouse_ids: List[int] = None) -> List[Dict[str, Any]]:
        """
        Получает коэффициенты приёмки для складов на ближайшие 14 дней.
        
        Args:
            warehouse_ids: Список ID складов (опционально, максимум 50 за раз)
            
        Returns:
            Список коэффициентов приёмки с датами и доступностью
        """
        logger.info("📊 Получаю коэффициенты приёмки")
        
        try:
            all_coefficients = []
            
            # Если складов нет, делаем запрос без параметров (по всем складам)
            if not warehouse_ids:
                response = await self._make_request("GET", "/acceptance/coefficients")
                if isinstance(response, list):
                    all_coefficients = response
                else:
                    all_coefficients = response.get("coefficients", [])
            else:
                # Разбиваем запрос на части по 20 складов (чтобы избежать таймаута)
                chunk_size = 20
                for i in range(0, len(warehouse_ids), chunk_size):
                    chunk = warehouse_ids[i:i + chunk_size]
                    params = {"warehouseIDs": ",".join(map(str, chunk))}
                    
                    logger.info(f"📊 Запрашиваю коэффициенты для {len(chunk)} складов (часть {i//chunk_size + 1})")
                    
                    response = await self._make_request("GET", "/acceptance/coefficients", params=params)
                    
                    if isinstance(response, list):
                        coefficients = response
                    else:
                        coefficients = response.get("coefficients", [])
                    
                    all_coefficients.extend(coefficients)
                    
                    # Небольшая пауза между запросами для соблюдения лимитов API
                    if i + chunk_size < len(warehouse_ids):
                        await asyncio.sleep(1)
            
            logger.info(f"✅ Получено коэффициентов всего: {len(all_coefficients)}")
            if all_coefficients:
                logger.info(f"🔍 Пример коэффициента: {all_coefficients[0]}")
            
            # Фильтруем доступные слоты (coefficient 0 или 1 и allowUnload = true)
            available_slots = []
            for coeff in all_coefficients:
                if (coeff.get("coefficient") in [0, 1] and 
                    coeff.get("allowUnload") is True):
                    available_slots.append({
                        "date": coeff.get("date"),
                        "warehouseID": coeff.get("warehouseID"),
                        "warehouseName": coeff.get("warehouseName"),
                        "coefficient": coeff.get("coefficient"),
                        "boxTypeName": coeff.get("boxTypeName"),
                        "boxTypeID": coeff.get("boxTypeID"),
                        "allowUnload": coeff.get("allowUnload"),
                        "isSortingCenter": coeff.get("isSortingCenter", False)
                    })
            
            logger.info(f"🎯 Найдено доступных слотов: {len(available_slots)}")
            return available_slots
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения коэффициентов приёмки: {e}")
            logger.error(f"❌ Тип ошибки: {type(e).__name__}")
            logger.error(f"❌ Детали ошибки: {str(e)}")
            # Возвращаем пустой список вместо raise, чтобы не ломать весь процесс
            return []
    
    async def get_supply_details(self, supply_id: str, is_preorder_id: bool = False) -> Dict[str, Any]:
        """
        Получает детальную информацию о поставке по официальному API WB.
        
        Args:
            supply_id: ID поставки или заказа
            is_preorder_id: True если передается ID заказа, False если ID поставки
            
        Returns:
            Детали поставки
        """
        logger.info(f"🔍 Получаю детали поставки: {supply_id} (preorder: {is_preorder_id})")
        
        try:
            # Используем правильный эндпоинт согласно документации WB
            params = {"isPreorderID": is_preorder_id} if is_preorder_id else {}
            
            response = await self._make_request(
                "GET", 
                f"/supplies/{supply_id}",
                params=params
            )
            logger.info(f"✅ Получены детали поставки {supply_id}: {response}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения деталей поставки {supply_id}: {e}")
            raise
    
    async def get_available_slots(self, warehouse_id: int, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """
        Получает доступные слоты для бронирования.
        
        Args:
            warehouse_id: ID склада
            date_from: Дата начала в формате YYYY-MM-DD
            date_to: Дата окончания в формате YYYY-MM-DD
            
        Returns:
            Список доступных слотов
        """
        logger.info(f"🕐 Получаю слоты для склада {warehouse_id} с {date_from} по {date_to}")
        
        try:
            response = await self._make_request(
                "GET", 
                "/acceptance/coefficients",
                params={
                    "warehouseId": warehouse_id,
                    "dateFrom": date_from,
                    "dateTo": date_to
                }
            )
            
            slots = response.get("coefficients", [])
            available_slots = [slot for slot in slots if slot.get("coefficient", 0) > 0]
            
            logger.info(f"✅ Найдено доступных слотов: {len(available_slots)}")
            return available_slots
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения слотов: {e}")
            raise
    
    async def create_supply_booking(self, supply_id: str, warehouse_id: int, date: str) -> bool:
        """
        Создает бронирование поставки.
        
        Args:
            supply_id: ID поставки
            warehouse_id: ID склада
            date: Дата в формате YYYY-MM-DD
            
        Returns:
            True если бронирование успешно
        """
        logger.info(f"📅 Создаю бронирование поставки {supply_id} на {date}")
        
        try:
            payload = {
                "supplyId": supply_id,
                "warehouseId": warehouse_id,
                "date": date
            }
            
            response = await self._make_request(
                "POST", 
                "/supplies/booking",
                json=payload
            )
            
            logger.info(f"✅ Бронирование создано успешно для поставки {supply_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бронирования: {e}")
            return False
    
    async def book_supply(
        self, 
        supply_id: str, 
        warehouse_id: int, 
        date: str, 
        time: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Бронирует поставку на указанную дату и время.
        
        Args:
            supply_id: ID поставки
            warehouse_id: ID склада
            date: Дата в формате YYYY-MM-DD
            time: Время слота (опционально)
            
        Returns:
            Результат бронирования или None при ошибке
        """
        logger.info(f"🎯 Бронирую поставку {supply_id} на склад {warehouse_id}, дата {date}, время {time}")
        
        try:
            payload = {
                "supplyId": supply_id,
                "warehouseId": warehouse_id,
                "date": date
            }
            
            if time:
                payload["time"] = time
            
            response = await self._make_request(
                "POST", 
                "/supplies/booking",
                json=payload
            )
            
            logger.info(f"✅ Поставка {supply_id} успешно забронирована")
            return {
                "success": True,
                "supply_id": supply_id,
                "date": date,
                "time": time,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка бронирования поставки {supply_id}: {e}")
            return None