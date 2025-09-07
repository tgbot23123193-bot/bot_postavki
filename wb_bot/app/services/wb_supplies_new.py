"""
Новый сервис для работы с поставками WB API.
Использует правильные эндпоинты и логику фильтрации.
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class WBSuppliesService:
    """Сервис для работы с поставками Wildberries."""
    
    def __init__(self):
        self.BASE_URL = "https://supplies-api.wildberries.ru"
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get_all_supplies(self, api_key: str) -> List[Dict]:
        """Получить ВСЕ поставки пользователя."""
        try:
            url = f"{self.BASE_URL}/api/v1/supplies"
            
            headers = {
                "Authorization": api_key,  # Без Bearer
                "Content-Type": "application/json"
            }
            
            # Формируем тело запроса по документации WB
            from datetime import datetime, timedelta
            
            # Запрашиваем поставки за последние 2 недели + год назад для полноты
            today = datetime.now()
            two_weeks_ago = today - timedelta(days=14)
            year_ago = today - timedelta(days=365)
            
            # Попробуем несколько вариантов запроса
            
            # Вариант 1: Без дат, только статусы
            request_body_1 = {
                "statusIDs": [1, 2, 3, 4, 5, 6]  # ВСЕ статусы без фильтра дат
            }
            
            # Вариант 2: Только один период createDate
            request_body_2 = {
                "dates": [
                    {
                        "from": year_ago.strftime("%Y-%m-%d"),
                        "till": today.strftime("%Y-%m-%d"), 
                        "type": "createDate"
                    }
                ],
                "statusIDs": [1, 2, 3, 4, 5, 6]
            }
            
            # Вариант 3: Широкий диапазон дат
            request_body_3 = {
                "dates": [
                    {
                        "from": "2020-01-01",
                        "till": "2030-12-31", 
                        "type": "createDate"
                    }
                ],
                "statusIDs": [1, 2, 3, 4, 5, 6]
            }
            
            # Пробуем варианты по очереди
            request_bodies = [
                ("Без дат", request_body_1),
                ("Год назад", request_body_2), 
                ("Широкий диапазон", request_body_3)
            ]
            
            for variant_name, request_body in request_bodies:
                print(f"🔍 Пробую вариант '{variant_name}': {request_body}")
                
                async with self.session.post(url, headers=headers, json=request_body) as response:
                    print(f"📡 Статус ответа для '{variant_name}': {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"📦 Тип данных: {type(data)}")
                        
                        # Проверяем структуру ответа
                        if isinstance(data, dict):
                            supplies_list = (
                                data.get('supplies') or 
                                data.get('data') or 
                                data.get('result') or 
                                data.get('items') or
                                []
                            )
                        else:
                            supplies_list = data if isinstance(data, list) else []
                        
                        print(f"✅ Вариант '{variant_name}' получил {len(supplies_list)} поставок")
                        
                        if len(supplies_list) > 0:
                            print(f"🎉 УСПЕХ! Используем вариант '{variant_name}'")
                            return supplies_list
                        else:
                            print(f"❌ Вариант '{variant_name}' вернул 0 поставок, пробуем следующий...")
                    else:
                        error_text = await response.text()
                        print(f"❌ Вариант '{variant_name}' failed {response.status}: {error_text}")
            
            print("💥 ВСЕ ВАРИАНТЫ FAILED - возвращаем пустой список")
            return []
                    
        except Exception as e:
            print(f"💥 Ошибка получения поставок: {e}")
            return []
    
    async def get_available_supplies_for_booking(self, api_key: str) -> List[Dict]:
        """Получить поставки доступные для бронирования."""
        all_supplies = await self.get_all_supplies(api_key)
        
        if not all_supplies:
            print("❌ Нет поставок от API")
            return []
        
        # Фильтруем поставки
        two_weeks_ago = datetime.now() - timedelta(days=14)
        available_supplies = []
        
        print(f"🔍 Анализирую {len(all_supplies)} поставок...")
        
        for i, supply in enumerate(all_supplies):
            if i < 5:  # Показываем первые 5 для отладки
                print(f"🔍 Поставка {i}: {supply}")
            
            supply_id = supply.get('supplyID', supply.get('id', supply.get('supplyId', f'unknown_{i}')))
            status_name = supply.get('statusName', supply.get('status', supply.get('state', '')))
            create_date_str = supply.get('createDate', supply.get('createdAt', supply.get('created', '')))
            supply_date_str = supply.get('supplyDate', supply.get('scheduledAt', supply.get('scheduled', '')))
            
            print(f"📋 Поставка {supply_id}: статус='{status_name}', создана='{create_date_str}', назначена='{supply_date_str}'")
            
            # Проверяем дату создания
            is_recent = False
            if create_date_str:
                try:
                    # Парсим разные форматы дат
                    if 'T' in create_date_str:
                        # ISO формат с временем
                        if '+' in create_date_str:
                            create_date = datetime.fromisoformat(create_date_str.split('+')[0])
                        elif 'Z' in create_date_str:
                            create_date = datetime.fromisoformat(create_date_str.replace('Z', ''))
                        else:
                            create_date = datetime.fromisoformat(create_date_str)
                    else:
                        # Только дата
                        create_date = datetime.strptime(create_date_str, '%Y-%m-%d')
                    
                    is_recent = create_date >= two_weeks_ago
                    print(f"📅 Дата создания: {create_date}, свежая: {is_recent}")
                    
                except Exception as e:
                    print(f"⚠️ Ошибка парсинга даты {create_date_str}: {e}")
                    is_recent = True  # Если не можем парсить - считаем свежей
            
            # Проверяем статус поставки
            status_lower = status_name.lower()
            
            # Статусы которые подходят для бронирования
            good_statuses = [
                'не запланировано', 'создано', 'новая', 'ожидает', 'draft', 'created', 
                'pending', 'на согласовании', 'черновик', 'создана', 'новый'
            ]
            
            # Статусы которые НЕ подходят (завершенные)
            bad_statuses = [
                'принято', 'завершено', 'отменено', 'закрыто', 'completed', 'cancelled', 
                'closed', 'delivered', 'доставлено', 'отклонено', 'rejected'
            ]
            
            is_good_status = any(good in status_lower for good in good_statuses)
            is_bad_status = any(bad in status_lower for bad in bad_statuses)
            is_no_schedule = not supply_date_str or supply_date_str.strip() == ''
            
            print(f"🎯 Анализ поставки {supply_id}:")
            print(f"   - Свежая (< 2 нед): {is_recent}")
            print(f"   - Хороший статус: {is_good_status}")
            print(f"   - Плохой статус: {is_bad_status}")
            print(f"   - Нет расписания: {is_no_schedule}")
            
            # Добавляем поставку если:
            # 1. Создана за последние 2 недели ИЛИ
            # 2. Имеет подходящий статус ИЛИ
            # 3. Не имеет назначенной даты поставки
            # И НЕ имеет завершающий статус
            
            should_include = (is_recent or is_good_status or is_no_schedule) and not is_bad_status
            
            if should_include:
                available_supplies.append(supply)
                print(f"✅ ДОБАВЛЕНА поставка {supply_id}")
            else:
                print(f"❌ ПРОПУЩЕНА поставка {supply_id}")
        
        print(f"🎉 Найдено {len(available_supplies)} поставок для бронирования из {len(all_supplies)} общих")
        return available_supplies
    
    async def get_supply_details(self, api_key: str, supply_id: str) -> Optional[Dict]:
        """Получить детали конкретной поставки."""
        try:
            url = f"{self.BASE_URL}/api/v1/supplies/{supply_id}"
            
            headers = {
                "Authorization": api_key,
                "Content-Type": "application/json"
            }
            
            print(f"🔍 Запрашиваю детали поставки {supply_id}: {url}")
            
            async with self.session.get(url, headers=headers) as response:
                print(f"📡 Статус ответа: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Получены детали поставки {supply_id}")
                    return data
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка получения деталей {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            print(f"💥 Ошибка получения деталей поставки {supply_id}: {e}")
            return None
