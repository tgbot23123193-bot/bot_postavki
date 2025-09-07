"""
Реальный сервис для работы с WB API v1.
Использует официальные эндпоинты из документации.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import aiohttp
import json

# Глобальная переменная для хранения API ключей
user_api_keys = {}


class WBRealAPI:
    """Сервис для работы с реальным API WB."""
    
    BASE_URL = "https://supplies-api.wildberries.ru"
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_warehouses(self, api_key: str) -> List[Dict]:
        """Получить список складов."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/api/v1/warehouses",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    print(f"ERROR getting warehouses: {resp.status} - {error_text}")
                    return []
        except Exception as e:
            print(f"ERROR in get_warehouses: {e}")
            return []
    
    async def get_acceptance_coefficients(
        self, 
        api_key: str, 
        warehouse_ids: Optional[List[int]] = None
    ) -> List[Dict]:
        """Получить коэффициенты приёмки для складов на ближайшие 14 дней."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        params = {}
        if warehouse_ids:
            params["warehouseIDs"] = ",".join(map(str, warehouse_ids))
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/api/v1/acceptance/coefficients",
                headers=headers,
                params=params
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    print(f"ERROR getting coefficients: {resp.status} - {error_text}")
                    return []
        except Exception as e:
            print(f"ERROR in get_acceptance_coefficients: {e}")
            return []
    
    async def get_acceptance_options(
        self,
        api_key: str,
        items: List[Dict[str, any]],
        warehouse_id: Optional[int] = None
    ) -> Dict:
        """Получить опции приёмки для товаров."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        params = {}
        if warehouse_id:
            params["warehouseID"] = str(warehouse_id)
        
        try:
            async with self.session.post(
                f"{self.BASE_URL}/api/v1/acceptance/options",
                headers=headers,
                params=params,
                json=items
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    print(f"ERROR getting options: {resp.status} - {error_text}")
                    return {"result": []}
        except Exception as e:
            print(f"ERROR in get_acceptance_options: {e}")
            return {"result": []}
    
    async def get_supplies_list(
        self,
        api_key: str,
        dates: Optional[List[Dict]] = None,
        status_ids: Optional[List[int]] = None
    ) -> List[Dict]:
        """Получить список поставок."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        body = {}
        if dates:
            body["dates"] = dates
        if status_ids:
            body["statusIDs"] = status_ids
        
        print(f"DEBUG: Requesting supplies with body: {body}")
        
        try:
            async with self.session.post(
                f"{self.BASE_URL}/api/v1/supplies",
                headers=headers,
                json=body if body else None  # Отправляем None если body пустой
            ) as resp:
                print(f"DEBUG: Response status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"DEBUG: Response data type: {type(data)}")
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # Может быть обернуто в объект
                        return data.get("supplies", data.get("result", []))
                    return []
                else:
                    error_text = await resp.text()
                    print(f"ERROR getting supplies: {resp.status} - {error_text}")
                    return []
        except Exception as e:
            print(f"ERROR in get_supplies_list: {e}")
            return []
    
    async def get_available_supplies_for_booking(self, api_key: str) -> List[Dict]:
        """Получить список поставок доступных для бронирования."""
        # Получаем все поставки для отладки
        from datetime import datetime, timedelta
        
        today = datetime.now()
        date_from = today - timedelta(days=365)  # Год назад
        date_till = today + timedelta(days=365)  # Год вперед
        
        # Используем createDate для поиска по дате создания поставки
        dates = [{
            "from": date_from.strftime("%Y-%m-%d"),
            "till": date_till.strftime("%Y-%m-%d"),
            "type": "createDate"  # По дате создания поставки
        }]
        
        # Фильтруем по статусу "Не запланировано" (ID: 5)
        supplies = await self.get_supplies_list(
            api_key=api_key,
            dates=dates,
            status_ids=[5]  # Только статус "Не запланировано"
        )
        
        print(f"DEBUG: Got {len(supplies)} supplies from API")
        
        # Если нет результатов, попробуем другой подход
        if not supplies:
            # Попробуем без дат но со статусом
            supplies = await self.get_supplies_list(
                api_key=api_key,
                dates=None,
                status_ids=[5]  # Только "Не запланировано"
            )
            print(f"DEBUG: Got {len(supplies)} supplies without date filter")
        
        # Выводим первые несколько для отладки
        for i, supply in enumerate(supplies[:3]):
            print(f"DEBUG Supply {i}: {supply}")
        
        # Фильтруем только поставки со статусом "Не запланировано"
        available_supplies = []
        for supply in supplies:
            status = supply.get("statusName", "")
            print(f"DEBUG: Checking supply {supply.get('supplyID')} with status: '{status}'")
            
            # Проверяем статус - нужны только "Не запланировано"
            if status and "не запланировано" in status.lower():
                available_supplies.append({
                    "supplyID": supply.get("supplyID"),
                    "preorderID": supply.get("preorderID"),
                    "createDate": supply.get("createDate"),
                    "supplyDate": supply.get("supplyDate"),
                    "statusName": status,
                    "phone": supply.get("phone", "")[:10] + "***" if supply.get("phone") else "Не указан"
                })
                print(f"DEBUG: Added supply {supply.get('supplyID')} to available list")
        
        print(f"DEBUG: Found {len(available_supplies)} supplies with status 'Не запланировано'")
        return available_supplies
    
    async def get_supply_details(self, api_key: str, supply_id: int) -> Optional[Dict]:
        """Получить детали поставки."""
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/api/v1/supplies/{supply_id}",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    print(f"ERROR getting supply details: {resp.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"ERROR in get_supply_details: {e}")
            return None
    
    async def find_available_slots(
        self,
        user_id: int,
        warehouse_id: int,
        supply_type: str = "boxes",
        max_coefficient: int = 0,
        days_ahead: int = 14
    ) -> List[Dict]:
        """Найти доступные слоты для поставки."""
        
        # Получаем API ключи пользователя
        api_keys = user_api_keys.get(user_id, [])
        if not api_keys:
            return []
        
        api_key = api_keys[0]
        results = []
        
        # Получаем коэффициенты приёмки
        coefficients = await self.get_acceptance_coefficients(api_key, [warehouse_id])
        
        for coef_data in coefficients:
            # Проверяем что это нужный склад
            if coef_data.get("warehouseID") != warehouse_id:
                continue
                
            # Проверяем доступность приёмки
            if not coef_data.get("allowUnload", False):
                continue
                
            # Проверяем коэффициент
            coefficient = coef_data.get("coefficient", -1)
            if coefficient < 0:
                continue
                
            if max_coefficient > 0 and coefficient > max_coefficient:
                continue
            
            # Проверяем тип упаковки
            box_type = coef_data.get("boxTypeName", "").lower()
            if supply_type == "boxes" and "короб" not in box_type.lower():
                continue
            elif supply_type == "mono" and "монопаллет" not in box_type.lower():
                continue
            
            # Добавляем слот
            date = coef_data.get("date", "")
            if date:
                # Преобразуем дату
                try:
                    date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    date_str = date_obj.strftime("%Y-%m-%d")
                except:
                    date_str = date[:10]  # Берем первые 10 символов
                
                results.append({
                    "date": date_str,
                    "time": "Весь день",
                    "coefficient": coefficient,
                    "warehouseId": warehouse_id,
                    "warehouseName": coef_data.get("warehouseName", ""),
                    "supplyType": supply_type,
                    "boxType": coef_data.get("boxTypeName", ""),
                    "boxTypeId": coef_data.get("boxTypeID", 0)
                })
        
        return results
    
    async def quick_search_all_warehouses(self, user_id: int) -> Dict[str, List[Dict]]:
        """Быстрый поиск по всем основным складам."""
        
        # Основные склады
        warehouses = {
            117986: "Коледино",
            507: "Подольск",
            120762: "Электросталь", 
            117501: "Казань",
            1733: "Екатеринбург",
            301: "СПб Шушары"
        }
        
        api_keys = user_api_keys.get(user_id, [])
        if not api_keys:
            return {}
            
        api_key = api_keys[0]
        
        # Получаем коэффициенты для всех складов сразу
        warehouse_ids = list(warehouses.keys())
        coefficients = await self.get_acceptance_coefficients(api_key, warehouse_ids)
        
        results = {}
        
        # Группируем по складам
        for coef_data in coefficients:
            warehouse_id = coef_data.get("warehouseID")
            if warehouse_id not in warehouses:
                continue
                
            warehouse_name = warehouses[warehouse_id]
            
            # Проверяем доступность
            if not coef_data.get("allowUnload", False):
                continue
                
            coefficient = coef_data.get("coefficient", -1)
            if coefficient < 0 or coefficient > 3:  # Только x0, x1, x2, x3
                continue
            
            # Преобразуем дату
            date = coef_data.get("date", "")
            if date:
                try:
                    date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    date_str = date_obj.strftime("%Y-%m-%d")
                except:
                    date_str = date[:10]
                
                if warehouse_name not in results:
                    results[warehouse_name] = []
                
                results[warehouse_name].append({
                    "date": date_str,
                    "time": "Весь день",
                    "coefficient": coefficient,
                    "warehouseId": warehouse_id,
                    "boxType": coef_data.get("boxTypeName", ""),
                    "allowUnload": True
                })
        
        return results


# Глобальный экземпляр сервиса
wb_real_api = WBRealAPI()
