"""
Сервис для работы с API складов и остатков Wildberries.
Получает данные о товарах и складах через API /api/v1/supplier/stocks
"""

import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ..utils.logger import get_logger
from ..services.database_service import db_service

logger = get_logger(__name__)


class WBStocksService:
    """Сервис для работы с API складов Wildberries."""
    
    def __init__(self):
        self.base_url = "https://statistics-api.wildberries.ru"
        self.stocks_endpoint = "/api/v1/supplier/stocks"
        
        # Список складов, участвующих в перераспределении
        self.allowed_warehouses = {
            "Коледино",
            "Казань", 
            "Электросталь",
            "Санкт-Петербург Уткина Завод",
            "Екатеринбург – Испытателей 14г",
            "Тула",
            "Невинномысск",
            "Рязань (Тюшевское)",
            "Котовск",
            "Волгоград",
            "Сарапул"
        }
    
    async def get_user_stocks(self, user_id: int, article: str = None) -> Dict[str, Any]:
        """
        Получает склады и остатки пользователя через API.
        
        Args:
            user_id: ID пользователя
            article: Артикул для фильтрации (опционально)
            
        Returns:
            Dict с результатом операции и данными о складах
        """
        try:
            logger.info(f"📊 Получение складов через API для пользователя {user_id}")
            
            # Получаем API ключ пользователя
            api_key = await self._get_user_api_key(user_id)
            if not api_key:
                return {
                    "success": False,
                    "error": "API ключ не найден. Добавьте ключ через меню 'API ключи'",
                    "user_id": user_id
                }
            
            # Формируем параметры запроса
            # dateFrom - обязательный параметр в формате RFC3339 (UTC+3 Москва)
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S')
            
            params = {
                'dateFrom': date_from  # Обязательный параметр для WB API
            }
            
            # НЕ фильтруем в API запросе - получаем ВСЕ товары, фильтрацию делаем в коде
            logger.info(f"📅 Запрос ВСЕХ товаров с даты: {date_from} (за последние 30 дней)")
            if article:
                logger.info(f"🔍 Будем фильтровать по артикулу: {article}")
            
            # Выполняем запрос к API
            headers = {
                'Authorization': api_key,
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🌐 Запрос к API: {self.base_url}{self.stocks_endpoint}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{self.stocks_endpoint}",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    logger.info(f"📡 Ответ API: статус {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Получено {len(data)} записей от API")
                        
                        # Обрабатываем данные
                        warehouses = await self._process_stocks_data(data, article)
                        
                        return {
                            "success": True,
                            "warehouses": warehouses,
                            "total_records": len(data),
                            "user_id": user_id,
                            "article": article
                        }
                    
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"🔑 Ошибка авторизации API: {error_text}")
                        return {
                            "success": False,
                            "error": "Неверный API ключ. Проверьте ключ в меню 'API ключи'",
                            "user_id": user_id,
                            "status_code": response.status
                        }
                    
                    elif response.status == 429:
                        logger.error(f"⏰ Превышен лимит запросов API")
                        return {
                            "success": False,
                            "error": "Превышен лимит запросов к API. Попробуйте позже",
                            "user_id": user_id,
                            "status_code": response.status
                        }
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка API: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"Ошибка API: {response.status}",
                            "user_id": user_id,
                            "status_code": response.status,
                            "error_details": error_text
                        }
        
        except asyncio.TimeoutError:
            logger.error(f"⏰ Таймаут запроса к API")
            return {
                "success": False,
                "error": "Таймаут запроса к API. Попробуйте позже",
                "user_id": user_id
            }
        
        except Exception as e:
            logger.error(f"❌ Ошибка при запросе к API: {e}")
            return {
                "success": False,
                "error": f"Ошибка получения данных: {str(e)}",
                "user_id": user_id
            }
    
    async def _get_user_api_key(self, user_id: int) -> Optional[str]:
        """Получает API ключ пользователя из базы данных."""
        try:
            # Прямой запрос к базе данных для получения активного API ключа
            from ..database.connection import get_session
            from ..database.models import APIKey
            from sqlalchemy import select
            
            async with get_session() as session:
                # Ищем активный и валидный API ключ пользователя
                stmt = select(APIKey).where(
                    APIKey.user_id == user_id,
                    APIKey.is_active == True,
                    APIKey.is_valid == True
                ).order_by(APIKey.last_used.desc().nullslast(), APIKey.created_at.desc())
                
                result = await session.execute(stmt)
                api_key_obj = result.scalar_one_or_none()
                
                if api_key_obj:
                    # Расшифровываем ключ
                    from ..utils.encryption import decrypt_api_key
                    decrypted_key = decrypt_api_key(api_key_obj.encrypted_key, api_key_obj.salt)
                    
                    logger.info(f"🔑 Найден активный API ключ для пользователя {user_id}")
                    
                    # Обновляем статистику использования
                    api_key_obj.last_used = datetime.utcnow()
                    api_key_obj.total_requests += 1
                    await session.commit()
                    
                    return decrypted_key
                else:
                    logger.warning(f"🔑 Активный API ключ не найден для пользователя {user_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения API ключа: {e}")
            return None
    
    async def _process_stocks_data(self, data: List[Dict], article: str = None) -> List[Dict[str, Any]]:
        """
        Обрабатывает данные о складах и остатках от API.
        
        Args:
            data: Сырые данные от API
            article: Артикул для фильтрации
            
        Returns:
            Список обработанных складов с остатками
        """
        try:
            logger.info(f"🔄 Обработка данных складов...")
            
            # Группируем данные по складам
            warehouses_data = {}
            
            # Для отладки - показываем первые 3 записи
            if len(data) > 0:
                logger.info(f"🔍 Пример данных от API (первые 3 записи):")
                for i, sample in enumerate(data[:3]):
                    logger.info(f"  Запись {i+1}: ALL_FIELDS = {sample}")
                    logger.info(f"    supplierArticle='{sample.get('supplierArticle')}', nmId={sample.get('nmId')}, barcode='{sample.get('barcode')}', warehouseName='{sample.get('warehouseName')}', quantity={sample.get('quantity')}, quantityFull={sample.get('quantityFull')}")
            
            for item in data:
                try:
                    # Основные поля
                    item_article = str(item.get('supplierArticle', ''))
                    item_nmid = str(item.get('nmId', ''))  # WB артикул
                    item_barcode = str(item.get('barcode', ''))
                    warehouse_name = item.get('warehouseName', 'Неизвестный склад')
                    quantity = item.get('quantity', 0)
                    quantity_full = item.get('quantityFull', 0)
                    
                    logger.info(f"📋 Проверяем: ищем '{article}', найден supplierArticle='{item_article}', nmId='{item_nmid}', barcode='{item_barcode}', склад '{warehouse_name}', остатки {quantity}/{quantity_full}")
                    
                    # Фильтруем по артикулу если указан - проверяем ВСЕ возможные поля
                    if article:
                        article_lower = article.lower()
                        if (article_lower != item_article.lower() and 
                            article != item_nmid and 
                            article != item_barcode):
                            logger.info(f"  ❌ Артикул не найден в supplierArticle, nmId, barcode")
                            continue
                        else:
                            logger.info(f"  ✅ Артикул найден! Поле с совпадением определено")
                    
                    # Пропускаем товары с нулевым остатком
                    if quantity <= 0 and quantity_full <= 0:
                        continue
                    
                    # Группируем по складу
                    if warehouse_name not in warehouses_data:
                        warehouses_data[warehouse_name] = {
                            'name': warehouse_name,
                            'total_quantity': 0,
                            'total_quantity_full': 0,
                            'articles': []
                        }
                    
                    # Добавляем данные по товару
                    warehouses_data[warehouse_name]['total_quantity'] += quantity
                    warehouses_data[warehouse_name]['total_quantity_full'] += quantity_full
                    warehouses_data[warehouse_name]['articles'].append({
                        'article': item_article,
                        'quantity': quantity,
                        'quantity_full': quantity_full,
                        'nm_id': item.get('nmId'),
                        'barcode': item.get('barcode', ''),
                        'subject': item.get('subject', ''),
                        'category': item.get('category', ''),
                        'brand': item.get('brand', ''),
                        'tech_size': item.get('techSize', ''),
                        'price': item.get('Price', 0),
                        'discount': item.get('Discount', 0),
                        'is_supply': item.get('isSupply', False),
                        'is_realization': item.get('isRealization', False),
                        'sku': item.get('SCCode', '')
                    })
                    
                except Exception as e:
                    logger.debug(f"Ошибка обработки элемента: {e}")
                    continue
            
            # Преобразуем в список со статистикой
            result_warehouses = []
            for warehouse_name, warehouse_data in warehouses_data.items():
                # Фильтруем только разрешенные склады для перераспределения
                if warehouse_name not in self.allowed_warehouses:
                    logger.info(f"🚫 Пропускаем склад '{warehouse_name}' - не участвует в перераспределении")
                    continue
                    
                articles_count = len(warehouse_data['articles'])
                
                warehouse_info = {
                    'id': f"api_warehouse_{len(result_warehouses)}",
                    'name': warehouse_name,
                    'quantity': warehouse_data['total_quantity'],
                    'quantity_full': warehouse_data['total_quantity_full'],
                    'articles_count': articles_count,
                    'articles': warehouse_data['articles'],
                    'source': 'api'
                }
                
                result_warehouses.append(warehouse_info)
                
                logger.info(f"📦 Склад: {warehouse_name}")
                logger.info(f"   📊 Остаток: {warehouse_data['total_quantity']} шт")
                logger.info(f"   📈 Полный остаток: {warehouse_data['total_quantity_full']} шт") 
                logger.info(f"   📋 Артикулов: {articles_count}")
            
            # Сортируем по количеству товаров (по убыванию)
            result_warehouses.sort(key=lambda x: x['quantity'], reverse=True)
            
            logger.info(f"✅ Обработано складов: {len(result_warehouses)}")
            return result_warehouses
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки данных складов: {e}")
            return []


# Глобальный экземпляр сервиса
wb_stocks_service = WBStocksService()


def get_wb_stocks_service() -> WBStocksService:
    """Возвращает экземпляр сервиса складов."""
    return wb_stocks_service
