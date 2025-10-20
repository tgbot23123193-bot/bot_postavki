// Content script for WB Deliveries Extension
// Runs on Wildberries pages to extract delivery information

class WBContentScript {
    constructor() {
        this.deliveries = [];
        this.autoCatchEnabled = false;
        this.autoCatchInterval = null;
        this.clickCount = 0;
        this.lastClickTime = null;
        this.redistributeEnabled = false;
        this.redistributeCount = 0;
        this.init();
    }

    init() {
        console.log('WB Extension: Content script loaded');
        
        // Listen for messages from popup
        chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
            this.handleMessage(request, sender, sendResponse);
            return true; // Will respond asynchronously
        });

        // Auto-scan on page load if on deliveries page
        if (this.isDeliveriesPage()) {
            setTimeout(() => {
                this.autoScan();
            }, 2000);
        }

        // Observe DOM changes for dynamic content
        this.observePageChanges();

        // Load auto-catch settings
        this.loadAutoCatchSettings();
    }

    handleMessage(request, sender, sendResponse) {
        switch (request.action) {
            case 'scanDeliveries':
                this.scanDeliveries().then(result => {
                    sendResponse(result);
                });
                break;
            
            case 'getPageInfo':
                sendResponse({
                    url: window.location.href,
                    isDeliveriesPage: this.isDeliveriesPage()
                });
                break;

            case 'startAutoCatch':
                console.log('📥 CONTENT: Получено сообщение startAutoCatch');
                console.log('   interval:', request.interval);
                console.log('   filters:', request.filters);
                this.startAutoCatch(request.interval, request.filters).then(result => {
                    sendResponse(result);
                });
                break;

            case 'stopAutoCatch':
                this.stopAutoCatch();
                sendResponse({ success: true });
                break;

            case 'getAutoCatchStatus':
                sendResponse({
                    enabled: this.autoCatchEnabled,
                    clickCount: this.clickCount,
                    lastClickTime: this.lastClickTime
                });
                break;

            case 'clickButton':
                this.clickPlanButton().then(result => {
                    sendResponse(result);
                });
                break;

            case 'debugCalendar':
                this.debugCalendar().then(result => {
                    sendResponse(result);
                });
                break;

            case 'startRedistribute':
                console.log('📥 CONTENT: Получено сообщение startRedistribute');
                console.log('   settings:', request.settings);
                this.startRedistribute(request.settings).then(result => {
                    sendResponse(result);
                });
                break;

            case 'stopRedistribute':
                this.stopRedistribute();
                sendResponse({ success: true });
                break;

            case 'testRedistributeClick':
                this.clickRedistributeButton().then(result => {
                    sendResponse(result);
                });
                break;

            case 'getRedistributeStatus':
                sendResponse({
                    enabled: this.redistributeEnabled,
                    count: this.redistributeCount
                });
                break;

            default:
                sendResponse({ success: false, error: 'Unknown action' });
        }
    }

    async debugCalendar() {
        console.log('=== НАЧАЛО ОТЛАДКИ КАЛЕНДАРЯ ===');
        
        const modals = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"], [class*="Modal"]');
        console.log(`Найдено модальных окон: ${modals.length}`);
        
        const allTds = document.querySelectorAll('td');
        console.log(`Всего TD элементов: ${allTds.length}`);
        
        // Проверяем разные селекторы
        const selectors = [
            'td[class*="Calendar-cell"]',
            'td[class*="calendar-cell"]',
            '.Calendar-cell',
            'td[class*="iW36qFTvl"]',
            'table td'
        ];
        
        const results = {};
        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            results[selector] = elements.length;
            console.log(`Селектор "${selector}": ${elements.length} элементов`);
        }
        
        // Выводим примеры классов TD
        if (allTds.length > 0) {
            console.log('Примеры классов TD:');
            Array.from(allTds).slice(0, 10).forEach((td, i) => {
                console.log(`  TD ${i}: classes="${td.className}", text="${td.textContent.substring(0, 50)}"`);
            });
        }
        
        // Ищем элементы с текстом даты
        const dateElements = Array.from(allTds).filter(td => {
            const text = td.textContent.trim();
            return /\d+\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/i.test(text);
        });
        
        console.log(`TD с текстом даты: ${dateElements.length}`);
        if (dateElements.length > 0) {
            console.log('Примеры TD с датами:');
            dateElements.slice(0, 3).forEach((td, i) => {
                console.log(`  ${i}: "${td.textContent.trim().substring(0, 100)}"`);
            });
        }
        
        console.log('=== КОНЕЦ ОТЛАДКИ КАЛЕНДАРЯ ===');
        
        return {
            success: true,
            modalsCount: modals.length,
            tdCount: allTds.length,
            calendarCells: dateElements.length,
            selectorResults: results
        };
    }

    isDeliveriesPage() {
        const url = window.location.href;
        return url.includes('supplies') || 
               url.includes('postavki') || 
               url.includes('delivery') ||
               url.includes('seller.wildberries.ru');
    }

    async autoScan() {
        if (!this.isDeliveriesPage()) return;

        try {
            const result = await this.scanDeliveries();
            if (result.success && result.count > 0) {
                this.showPageNotification(`Найдено поставок: ${result.count}`);
            }
        } catch (error) {
            console.error('Auto-scan error:', error);
        }
    }

    async scanDeliveries() {
        console.log('WB Extension: Scanning deliveries...');

        try {
            const deliveries = this.extractDeliveries();
            
            if (deliveries.length === 0) {
                // Try alternative selectors
                const alternativeDeliveries = this.extractDeliveriesAlternative();
                if (alternativeDeliveries.length > 0) {
                    deliveries.push(...alternativeDeliveries);
                }
            }

            // Save to storage
            await this.saveDeliveries(deliveries);

            // Update statistics
            await this.updateStatistics(deliveries);

            // Notify background script
            chrome.runtime.sendMessage({
                action: 'deliveriesScanned',
                count: deliveries.length
            });

            return {
                success: true,
                count: deliveries.length,
                deliveries: deliveries
            };
        } catch (error) {
            console.error('Error scanning deliveries:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    extractDeliveries() {
        const deliveries = [];
        
        // Method 1: Try to find table rows with delivery information
        const rows = document.querySelectorAll('tr[data-supply], .supply-row, .delivery-item, [class*="supply"]');
        
        rows.forEach((row, index) => {
            try {
                const delivery = this.parseDeliveryRow(row, index);
                if (delivery) {
                    deliveries.push(delivery);
                }
            } catch (error) {
                console.warn('Error parsing delivery row:', error);
            }
        });

        // Method 2: Try JSON data in page
        const scriptTags = document.querySelectorAll('script[type="application/json"]');
        scriptTags.forEach(script => {
            try {
                const data = JSON.parse(script.textContent);
                if (data.supplies || data.deliveries) {
                    const items = data.supplies || data.deliveries;
                    items.forEach(item => {
                        deliveries.push(this.normalizeDelivery(item));
                    });
                }
            } catch (error) {
                // Not valid JSON or not delivery data
            }
        });

        return deliveries;
    }

    extractDeliveriesAlternative() {
        const deliveries = [];

        // Try to find any elements that might contain delivery info
        const possibleContainers = document.querySelectorAll(
            '[class*="supply"], [class*="delivery"], [class*="order"], ' +
            '[id*="supply"], [id*="delivery"], [id*="order"]'
        );

        possibleContainers.forEach((container, index) => {
            const text = container.textContent;
            
            // Look for delivery ID patterns
            const idMatch = text.match(/WB-\d+|№\s*(\d+)|ID:\s*(\d+)/i);
            if (idMatch) {
                const delivery = {
                    id: idMatch[1] || idMatch[2] || `extracted-${index}`,
                    status: this.extractStatus(text),
                    createdAt: this.extractDate(text) || Date.now(),
                    source: 'alternative',
                    rawText: text.substring(0, 200)
                };
                deliveries.push(delivery);
            }
        });

        return deliveries;
    }

    parseDeliveryRow(row, index) {
        const cells = row.querySelectorAll('td, .cell, [class*="cell"]');
        
        // Try to extract delivery ID
        let id = row.getAttribute('data-id') || 
                 row.getAttribute('data-supply-id') ||
                 this.findTextMatch(row, /WB-\d+|№\s*(\d+)/);

        if (!id) {
            id = `delivery-${Date.now()}-${index}`;
        }

        // Extract status
        const status = this.extractStatus(row.textContent);

        // Extract dates
        const dateText = row.textContent;
        const createdAt = this.extractDate(dateText) || Date.now();

        // Extract items count
        const itemsCount = this.extractNumber(dateText);

        // Get deadline if exists
        const deadline = this.extractDeadline(row);

        return {
            id: id,
            status: status,
            createdAt: createdAt,
            deadline: deadline,
            itemsCount: itemsCount,
            scannedAt: Date.now(),
            url: window.location.href
        };
    }

    normalizeDelivery(item) {
        return {
            id: item.id || item.supplyId || item.deliveryId || `norm-${Date.now()}`,
            status: this.mapStatus(item.status || item.state),
            createdAt: item.createdAt || item.created || Date.now(),
            deadline: item.deadline || item.dueDate,
            itemsCount: item.itemsCount || item.quantity,
            scannedAt: Date.now(),
            url: window.location.href,
            originalData: item
        };
    }

    extractStatus(text) {
        const statusMap = {
            'активн': 'active',
            'active': 'active',
            'в работе': 'active',
            'ожидает': 'pending',
            'pending': 'pending',
            'новая': 'pending',
            'завершен': 'completed',
            'completed': 'completed',
            'доставлен': 'completed',
            'отменен': 'cancelled',
            'cancelled': 'cancelled'
        };

        const lowerText = text.toLowerCase();
        for (const [key, value] of Object.entries(statusMap)) {
            if (lowerText.includes(key)) {
                return value;
            }
        }

        return 'active'; // Default status
    }

    mapStatus(status) {
        if (!status) return 'active';
        
        const statusMap = {
            '0': 'pending',
            '1': 'active',
            '2': 'completed',
            '3': 'cancelled',
            'new': 'pending',
            'in_progress': 'active',
            'done': 'completed'
        };

        return statusMap[status.toString().toLowerCase()] || 'active';
    }

    extractDate(text) {
        // Try to match Russian date format: DD.MM.YYYY or DD.MM.YY
        const dateMatch = text.match(/(\d{1,2})\.(\d{1,2})\.(\d{2,4})/);
        if (dateMatch) {
            const [, day, month, year] = dateMatch;
            const fullYear = year.length === 2 ? `20${year}` : year;
            return new Date(`${fullYear}-${month}-${day}`).getTime();
        }

        // Try ISO format
        const isoMatch = text.match(/\d{4}-\d{2}-\d{2}/);
        if (isoMatch) {
            return new Date(isoMatch[0]).getTime();
        }

        return null;
    }

    extractDeadline(element) {
        const text = element.textContent;
        const deadlineWords = ['дедлайн', 'deadline', 'до', 'срок'];
        
        for (const word of deadlineWords) {
            if (text.toLowerCase().includes(word)) {
                const dateMatch = text.match(/(\d{1,2})\.(\d{1,2})\.(\d{2,4})/g);
                if (dateMatch && dateMatch.length > 0) {
                    const lastDate = dateMatch[dateMatch.length - 1];
                    return this.extractDate(lastDate);
                }
            }
        }

        return null;
    }

    extractNumber(text) {
        const numbers = text.match(/\d+/g);
        if (numbers && numbers.length > 0) {
            return parseInt(numbers[0]);
        }
        return null;
    }

    findTextMatch(element, regex) {
        const match = element.textContent.match(regex);
        return match ? match[0] : null;
    }

    async saveDeliveries(deliveries) {
        // Get existing deliveries
        const data = await chrome.storage.local.get(['deliveries']);
        const existingDeliveries = data.deliveries || [];

        // Merge with existing, avoiding duplicates
        const deliveryMap = new Map();
        
        existingDeliveries.forEach(d => deliveryMap.set(d.id, d));
        deliveries.forEach(d => {
            const existing = deliveryMap.get(d.id);
            if (existing) {
                // Update existing delivery
                deliveryMap.set(d.id, { ...existing, ...d, updatedAt: Date.now() });
            } else {
                deliveryMap.set(d.id, d);
            }
        });

        const mergedDeliveries = Array.from(deliveryMap.values());
        
        await chrome.storage.local.set({ 
            deliveries: mergedDeliveries,
            lastScan: Date.now()
        });

        console.log(`Saved ${mergedDeliveries.length} deliveries`);
    }

    async updateStatistics(deliveries) {
        const stats = {
            active: deliveries.filter(d => d.status === 'active').length,
            pending: deliveries.filter(d => d.status === 'pending').length,
            completed: deliveries.filter(d => d.status === 'completed').length,
            total: deliveries.length
        };

        await chrome.storage.local.set({ stats });
    }

    observePageChanges() {
        const observer = new MutationObserver((mutations) => {
            // Debounce multiple changes
            clearTimeout(this.observerTimeout);
            this.observerTimeout = setTimeout(() => {
                console.log('Page content changed, might need to rescan');
            }, 1000);
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    showPageNotification(message) {
        // Create floating notification on the page
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999999;
            animation: slideInRight 0.3s ease;
        `;
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 20px;">📦</span>
                <span>${message}</span>
            </div>
        `;

        // Add animation styles
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideInRight {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOutRight {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(400px);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    // Method to inject a button on WB pages for quick access
    injectQuickAccessButton() {
        const button = document.createElement('button');
        button.id = 'wb-extension-quick-scan';
        button.innerHTML = '📦 Сканировать поставки';
        button.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 999998;
            transition: transform 0.2s;
        `;

        button.addEventListener('mouseenter', () => {
            button.style.transform = 'scale(1.05)';
        });

        button.addEventListener('mouseleave', () => {
            button.style.transform = 'scale(1)';
        });

        button.addEventListener('click', async () => {
            button.innerHTML = '⏳ Сканирование...';
            button.disabled = true;
            
            const result = await this.scanDeliveries();
            
            if (result.success) {
                this.showPageNotification(`✅ Найдено поставок: ${result.count}`);
            } else {
                this.showPageNotification('❌ Ошибка сканирования');
            }

            button.innerHTML = '📦 Сканировать поставки';
            button.disabled = false;
        });

        // Only inject if not already present
        if (!document.getElementById('wb-extension-quick-scan') && this.isDeliveriesPage()) {
            document.body.appendChild(button);
        }
    }

    // ============= AUTO-CATCH METHODS =============

    async loadAutoCatchSettings() {
        try {
            const settings = await chrome.storage.local.get(['autoCatchEnabled', 'autoCatchInterval']);
            
            if (settings.autoCatchEnabled) {
                this.startAutoCatch(settings.autoCatchInterval || 1000);
            }
        } catch (error) {
            console.log('Could not load auto-catch settings:', error);
        }
    }

    async startAutoCatch(interval = 1000, filters = {}) {
        console.log('═══════════════════════════════════════════');
        console.log('🎯 ЗАПУСК АВТОЛОВЛИ');
        console.log('═══════════════════════════════════════════');
        console.log('⏱️ Интервал:', interval, 'мс');
        console.log('📋 Полученные фильтры:', JSON.stringify(filters, null, 2));
        
        this.autoCatchEnabled = true;
        this.clickCount = 0;
        this.lastClickTime = null;
        this.filters = filters;

        // Логируем выбранную пользователем дату
        if (filters.dateMode === 'specific' && filters.specificDate) {
            const userDate = new Date(filters.specificDate);
            console.log('📅 ПОЛЬЗОВАТЕЛЬ ВЫБРАЛ ДАТУ:', userDate.toLocaleDateString('ru-RU'));
            console.log('   День:', userDate.getDate());
            console.log('   Месяц:', userDate.getMonth() + 1);
            console.log('   Год:', userDate.getFullYear());
        } else if (filters.dateMode === 'range') {
            console.log('📅 ПОЛЬЗОВАТЕЛЬ ВЫБРАЛ ДИАПАЗОН:');
            console.log('   От:', filters.dateFrom);
            console.log('   До:', filters.dateTo);
        } else {
            console.log('📅 ПОЛЬЗОВАТЕЛЬ ВЫБРАЛ: Любая дата');
        }

        if (filters.filterByCoefficient) {
            console.log('💰 ФИЛЬТР ПО КОЭФФИЦИЕНТУ:');
            console.log('   От:', filters.coefficientFrom);
            console.log('   До:', filters.coefficientTo);
            console.log('   Бесплатно:', filters.allowFree ? 'ДА' : 'НЕТ');
        }

        console.log('📦 ТИП УПАКОВКИ:', filters.boxType === 'monopallet' ? 'Монопаллеты' : 'Короба');
        if (filters.boxType === 'monopallet') {
            console.log('   Количество монопаллет:', filters.monopalletCount);
        }
        console.log('═══════════════════════════════════════════');

        // Save settings
        await chrome.storage.local.set({
            autoCatchEnabled: true,
            autoCatchInterval: interval,
            autoCatchFilters: filters
        });

        // Clear existing interval
        if (this.autoCatchInterval) {
            clearInterval(this.autoCatchInterval);
        }

        // Show notification
        this.showPageNotification('🎯 Автоловля поставок запущена!');

        // Start clicking
        this.autoCatchInterval = setInterval(async () => {
            if (this.autoCatchEnabled) {
                await this.clickPlanButton();
            }
        }, interval);

        // Send message to background
        chrome.runtime.sendMessage({
            action: 'autoCatchStarted',
            interval: interval
        });

        return { success: true, enabled: true };
    }

    async stopAutoCatch() {
        console.log('🛑 Stopping auto-catch');
        
        this.autoCatchEnabled = false;

        if (this.autoCatchInterval) {
            clearInterval(this.autoCatchInterval);
            this.autoCatchInterval = null;
        }

        // Save settings
        await chrome.storage.local.set({
            autoCatchEnabled: false
        });

        // Show notification
        this.showPageNotification(`🛑 Автоловля остановлена. Кликов: ${this.clickCount}`);

        // Send message to background
        chrome.runtime.sendMessage({
            action: 'autoCatchStopped',
            clickCount: this.clickCount
        });
    }

    async clickPlanButton() {
        try {
            // Найти кнопку "Запланировать поставку" по различным селекторам
            const button = this.findPlanButton();

            if (button) {
                // Проверяем, доступна ли кнопка
                if (button.disabled || button.classList.contains('disabled')) {
                    console.log('⚠️ Кнопка недоступна');
                    return { success: false, reason: 'disabled' };
                }

                // Симулируем клик
                this.simulateClick(button);

                this.clickCount++;
                this.lastClickTime = Date.now();

                console.log(`✅ Клик #${this.clickCount} по кнопке "Запланировать поставку"`);

                // Сохраняем статистику
                await this.saveClickStats();

                // Отправляем уведомление
                chrome.runtime.sendMessage({
                    action: 'buttonClicked',
                    clickCount: this.clickCount,
                    timestamp: this.lastClickTime
                });

                // Проверяем, не открылось ли модальное окно или новая страница
                setTimeout(() => {
                    this.checkForSuccess();
                }, 500);

                return { 
                    success: true, 
                    clickCount: this.clickCount,
                    timestamp: this.lastClickTime
                };
            } else {
                console.log('❌ Кнопка "Запланировать поставку" не найдена');
                return { success: false, reason: 'not_found' };
            }
        } catch (error) {
            console.error('Ошибка при клике:', error);
            return { success: false, error: error.message };
        }
    }

    findPlanButton() {
        // Метод 1: По классам из скриншота
        let button = document.querySelector('button.button_ymbakhzRx');
        if (button) return button;

        // Метод 2: По тексту кнопки (гибкий поиск)
        const buttons = Array.from(document.querySelectorAll('button'));
        button = buttons.find(btn => {
            const text = btn.textContent.toLowerCase().trim();
            return text.includes('запланировать') || 
                   text.includes('поставку') ||
                   text.includes('запланировать поставку');
        });
        if (button) return button;

        // Метод 3: По другим возможным классам
        const selectors = [
            'button[class*="fullWidth"]',
            'button[class*="TwrfVPCWJP"]',
            'button[class*="KLcGD7"]',
            'button.m_w-c',
            '[data-testid*="plan"]',
            '[data-testid*="supply"]',
            'button[type="button"]'
        ];

        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            for (const el of elements) {
                const text = el.textContent.toLowerCase();
                if (text.includes('запланировать') || text.includes('поставку')) {
                    return el;
                }
            }
        }

        return null;
    }

    simulateClick(element) {
        // Множественные типы событий для надежности
        const events = ['mousedown', 'mouseup', 'click'];
        
        events.forEach(eventType => {
            const event = new MouseEvent(eventType, {
                view: window,
                bubbles: true,
                cancelable: true,
                buttons: 1
            });
            element.dispatchEvent(event);
        });

        // Также пробуем нативный клик
        element.click();

        // Добавляем визуальную индикацию клика
        this.highlightElement(element);
    }

    highlightElement(element) {
        const originalBorder = element.style.border;
        const originalBoxShadow = element.style.boxShadow;
        
        element.style.border = '3px solid #10b981';
        element.style.boxShadow = '0 0 20px rgba(16, 185, 129, 0.6)';
        
        setTimeout(() => {
            element.style.border = originalBorder;
            element.style.boxShadow = originalBoxShadow;
        }, 300);
    }

    async checkForSuccess() {
        try {
            // Проверяем, что автоловля еще активна
            if (!this.autoCatchEnabled) {
                console.log('⚠️ Автоловля уже остановлена, пропускаем проверку');
                return;
            }

            console.log('🔍 Проверяем, открылось ли модальное окно...');
            
            // Ждем немного, чтобы DOM успел обновиться
            await this.sleep(300);
            
            // Проверяем, открылось ли модальное окно или календарь
            const modals = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"], [class*="Modal"]');
            
            console.log(`Найдено модальных окон: ${modals.length}`);
            
            if (modals.length > 0) {
                console.log('✅ Модальное окно открылось!');
                
                // Ждем загрузки календаря с более широким набором селекторов
                console.log('⏳ Ждем появления календаря...');
                const calendar = await this.waitForCalendar(5000);
                
                if (calendar) {
                    console.log('✅ Календарь найден!');
                    
                    // Небольшая задержка для полной загрузки
                    await this.sleep(800);
                    
                    // Начинаем поиск подходящей даты
                    await this.findAndSelectDate();
                } else {
                    console.log('❌ Календарь не найден в течение 5 секунд');
                    // Закрываем модалку и продолжаем цикл
                    await this.closeModal();
                }
            } else {
                console.log('⚠️ Модальное окно не найдено');
            }
        } catch (error) {
            console.error('Ошибка в checkForSuccess:', error);
        }
    }

    async waitForCalendar(timeout = 5000) {
        console.log('🔍 Ищем календарь...');
        const startTime = Date.now();
        
        const selectors = [
            'td[class*="Calendar-cell"]',
            'td[class*="calendar-cell"]',
            '.Calendar-cell',
            '[class*="Calendar"] td',
            'table td[class*="cell"]',
            'td[data-date]',
            'td[class*="iW36qFTvl"]',
            'td[class*="lendar-cell"]'
        ];
        
        while (Date.now() - startTime < timeout) {
            for (const selector of selectors) {
                const elements = document.querySelectorAll(selector);
                if (elements.length > 0) {
                    console.log(`✅ Календарь найден по селектору: ${selector}, ячеек: ${elements.length}`);
                    return elements[0];
                }
            }
            
            // Логируем каждую секунду для отладки
            if (Math.floor((Date.now() - startTime) / 1000) % 1 === 0) {
                console.log(`⏳ Ждем календарь... (${Math.floor((Date.now() - startTime) / 1000)}с)`);
            }
            
            await this.sleep(200);
        }
        
        console.log('❌ Календарь не найден. Попробуем найти любые td в документе...');
        const allTds = document.querySelectorAll('td');
        console.log(`Всего TD элементов на странице: ${allTds.length}`);
        
        if (allTds.length > 0) {
            console.log('Примеры классов TD:', 
                Array.from(allTds).slice(0, 5).map(td => td.className).filter(c => c));
        }
        
        return null;
    }

    async findAndSelectDate() {
        console.log('');
        console.log('═══════════════════════════════════════════');
        console.log('🔍 ПОИСК И ВЫБОР ДАТЫ');
        console.log('═══════════════════════════════════════════');

        // Показываем, что ищем
        if (this.filters) {
            if (this.filters.dateMode === 'specific' && this.filters.specificDate) {
                const targetDate = new Date(this.filters.specificDate);
                console.log('🎯 ИЩЕМ ДАТУ:', targetDate.toLocaleDateString('ru-RU'));
                console.log('   (день:', targetDate.getDate(), ', месяц:', targetDate.getMonth() + 1, ', год:', targetDate.getFullYear() + ')');
            } else if (this.filters.dateMode === 'range') {
                console.log('🎯 ИЩЕМ ДИАПАЗОН:', this.filters.dateFrom, '-', this.filters.dateTo);
            } else {
                console.log('🎯 ИЩЕМ: Любую дату');
            }
        } else {
            console.log('⚠️ ФИЛЬТРЫ НЕ УСТАНОВЛЕНЫ!');
        }

        try {
            // Пробуем разные селекторы для поиска ячеек календаря
            let calendarCells = [];
            
            const selectors = [
                'td[class*="Calendar-cell"]',
                'td[class*="calendar-cell"]',
                '.Calendar-cell',
                '[class*="Calendar"] td',
                'table td[class*="cell"]',
                'td[data-date]',
                'td[class*="iW36qFTvl"]'
            ];
            
            for (const selector of selectors) {
                calendarCells = document.querySelectorAll(selector);
                if (calendarCells.length > 0) {
                    console.log(`✅ Ячейки найдены по селектору: ${selector}`);
                    break;
                }
            }
            
            if (calendarCells.length === 0) {
                console.log('❌ Ячейки календаря не найдены по стандартным селекторам');
                console.log('🔍 Ищем по всему DOM...');
                
                // Последняя попытка - ищем любые td с текстом даты
                const allTds = document.querySelectorAll('td');
                console.log(`   Найдено всего TD: ${allTds.length}`);
                
                // Фильтруем те, что похожи на даты
                calendarCells = Array.from(allTds).filter(td => {
                    const text = td.textContent.trim();
                    return /\d+\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/i.test(text);
                });
                
                console.log(`   Найдено TD с датами: ${calendarCells.length}`);
                
                if (calendarCells.length === 0) {
                    this.showPageNotification('❌ Не удалось найти календарь', 'error');
                    return false;
                }
            }

            console.log(`📅 ВСЕГО ЯЧЕЕК КАЛЕНДАРЯ: ${calendarCells.length}`);

            // Собираем все даты с информацией
            console.log('');
            console.log('📊 ИЗВЛЕКАЕМ ИНФОРМАЦИЮ ИЗ ЯЧЕЕК:');
            console.log('─────────────────────────────────────────');
            
            const allDates = [];
            const unavailableDates = [];
            
            for (let i = 0; i < calendarCells.length; i++) {
                const cell = calendarCells[i];
                const dateInfo = await this.extractDateInfo(cell);
                
                if (dateInfo && dateInfo.parsedDate) {
                    if (dateInfo.isAvailable) {
                        console.log(`  ${i + 1}. ✅ ${dateInfo.dateText} → ${dateInfo.parsedDate.toLocaleDateString('ru-RU')} (${dateInfo.acceptance})`);
                        allDates.push(dateInfo);
                    } else {
                        unavailableDates.push(dateInfo.dateText);
                    }
                }
            }
            
            if (unavailableDates.length > 0) {
                console.log(`  ⚠️ Пропущено недоступных дат: ${unavailableDates.length}`);
            }

            console.log('─────────────────────────────────────────');
            console.log(`📅 ДОСТУПНЫХ ДАТ: ${allDates.length} | НЕДОСТУПНЫХ: ${unavailableDates.length}`);
            console.log('');

            if (allDates.length === 0) {
                console.log('');
                console.log('═══════════════════════════════════════════');
                console.log('❌ НЕТ ДОСТУПНЫХ ДАТ В КАЛЕНДАРЕ!');
                console.log('═══════════════════════════════════════════');
                console.log('🔄 Закрываем модалку и повторяем цикл...');
                
                await this.closeModal();
                await this.sleep(500);
                
                console.log('♻️ Цикл продолжается...');
                console.log('');
                
                return false;
            }

            // Фильтруем даты по критериям
            console.log('🔍 ФИЛЬТРАЦИЯ ДАТ:');
            console.log('─────────────────────────────────────────');
            
            const matchingDates = [];
            for (const dateInfo of allDates) {
                const matches = await this.matchesFilters(dateInfo);
                const emoji = matches ? '✅' : '❌';
                const status = matches ? 'ПОДХОДИТ' : 'не подходит';
                console.log(`${emoji} ${dateInfo.dateText} (${dateInfo.parsedDate.toLocaleDateString('ru-RU')}) - ${status}`);
                
                if (matches) {
                    matchingDates.push(dateInfo);
                }
            }

            console.log('─────────────────────────────────────────');
            console.log(`✅ НАЙДЕНО ПОДХОДЯЩИХ ДАТ: ${matchingDates.length}`);

            console.log('');

            if (matchingDates.length === 0) {
                console.log('');
                console.log('═══════════════════════════════════════════');
                console.log('❌ ПОДХОДЯЩАЯ ДАТА НЕ НАЙДЕНА!');
                console.log('═══════════════════════════════════════════');
                console.log('🔄 Закрываем модалку и повторяем цикл...');
                
                // Закрываем модальное окно
                await this.closeModal();
                
                // Небольшая пауза перед следующей попыткой
                await this.sleep(500);
                
                console.log('♻️ Цикл продолжается...');
                console.log('');
                
                // Не останавливаем автоловлю - продолжаем цикл
                return false;
            }

            // Сортируем даты по возрастанию (самая ближайшая первой)
            matchingDates.sort((a, b) => a.parsedDate - b.parsedDate);

            console.log('🎯 ПОДХОДЯЩИЕ ДАТЫ (отсортированные):');
            matchingDates.forEach((d, i) => {
                console.log(`   ${i + 1}. ${d.dateText} - ${d.parsedDate.toLocaleDateString('ru-RU')} (коэф: ${d.coefficient}${d.isFree ? ' бесплатно' : ''})`);
            });

            // Берем первую подходящую дату
            const selectedDate = matchingDates[0];
            console.log('');
            console.log('═══════════════════════════════════════════');
            console.log('✅ ВЫБИРАЕМ ДАТУ:', selectedDate.dateText);
            console.log('   Полная дата:', selectedDate.parsedDate.toLocaleDateString('ru-RU'));
            console.log('   Коэффициент:', selectedDate.acceptance);
            console.log('═══════════════════════════════════════════');

            // Выбираем эту дату
            const success = await this.selectDate(selectedDate.cell);
            
            if (success) {
                console.log('✅ УСПЕХ! Дата выбрана:', selectedDate.dateText);
                
                // Если выбраны монопаллеты - вводим количество
                if (this.filters.boxType === 'monopallet') {
                    console.log('');
                    console.log('📦 ТИП УПАКОВКИ: МОНОПАЛЛЕТЫ');
                    console.log('   Вводим количество:', this.filters.monopalletCount);
                    
                    await this.sleep(500);
                    const inputSuccess = await this.enterMonopalletCount(this.filters.monopalletCount);
                    
                    if (!inputSuccess) {
                        console.log('⚠️ Не удалось ввести количество монопаллет');
                        await this.closeModal();
                        return false;
                    }
                }
                
                // Ждем немного и нажимаем кнопку "Запланировать" (финальная)
                await this.sleep(800);
                const planned = await this.clickFinalPlanButton();
                
                if (planned) {
                    console.log('');
                    console.log('═══════════════════════════════════════════');
                    console.log('🎉 ПОСТАВКА УСПЕШНО ЗАПЛАНИРОВАНА!');
                    console.log('   Дата:', selectedDate.dateText);
                    console.log('   Коэффициент:', selectedDate.acceptance);
                    console.log('   Всего кликов:', this.clickCount);
                    console.log('═══════════════════════════════════════════');
                    
                    this.showPageNotification(`🎉 Успех! ${selectedDate.dateText}`, 'success');
                    
                    // НЕ останавливаем автоловлю - продолжаем искать еще слоты!
                    // Пользователь может хотеть поймать несколько слотов
                    
                    // Уведомляем background для отправки в Telegram
                    chrome.runtime.sendMessage({
                        action: 'sendNotification',
                        title: '🎉 Поставка запланирована!',
                        message: `Дата: ${selectedDate.dateText}\nКоэффициент: ${selectedDate.acceptance}x\nКликов: ${this.clickCount}`,
                        data: {
                            type: 'supply_planned',
                            date: selectedDate.dateText,
                            coefficient: selectedDate.acceptance,
                            clickCount: this.clickCount
                        }
                    });
                    
                    // Увеличиваем счетчик успешных бронирований
                    const stats = await chrome.storage.local.get(['autoCatchStats']);
                    const currentStats = stats.autoCatchStats || { totalBookings: 0 };
                    currentStats.totalBookings = (currentStats.totalBookings || 0) + 1;
                    await chrome.storage.local.set({ autoCatchStats: currentStats });
                    
                    return true;
                } else {
                    console.log('');
                    console.log('⚠️ НЕ УДАЛОСЬ НАЖАТЬ ФИНАЛЬНУЮ "ЗАПЛАНИРОВАТЬ"');
                    console.log('🔄 Закрываем модалку и повторяем цикл...');
                    
                    // Закрываем и повторяем
                    await this.closeModal();
                    await this.sleep(300);
                }
                
                return true;
            }
            
        } catch (error) {
            console.error('Ошибка при поиске даты:', error);
        }

        return false;
    }

    async extractDateInfo(cell) {
        try {
            // Проверяем, доступна ли дата для бронирования
            const cellText = cell.textContent.trim();
            
            // Проверка на "Пока недоступно"
            if (cellText.includes('Пока недоступно') || 
                cellText.includes('недоступно') ||
                cellText.includes('Недоступно')) {
                console.log(`   ⚠️ Пропускаем: дата недоступна`);
                return null;
            }
            
            // Извлекаем текст даты (например: "13 октября, пн")
            let dateSpan = cell.querySelector('span.Text_mexx[class*="Text--body"]');
            
            // Пробуем альтернативные селекторы
            if (!dateSpan) {
                dateSpan = cell.querySelector('span[class*="Text"]');
            }
            if (!dateSpan) {
                dateSpan = cell.querySelector('span');
            }
            
            if (!dateSpan) {
                // Используем весь текст ячейки
                if (cellText && /\d+\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/i.test(cellText)) {
                    const dateText = cellText.split('\n')[0].trim(); // Берем первую строку
                    const acceptanceInfo = this.extractAcceptanceInfo(cell);
                    
                    // Если нет информации о приемке и дата "недоступна"
                    if (acceptanceInfo.text === 'Неизвестно' || acceptanceInfo.text === 'Пока недоступно') {
                        console.log(`   ⚠️ Пропускаем "${dateText}": нет данных о приемке`);
                        return null;
                    }
                    
                    const parsedDate = this.parseRussianDate(dateText);
                    
                    return {
                        dateText: dateText,
                        parsedDate: parsedDate,
                        acceptance: acceptanceInfo.text,
                        coefficient: acceptanceInfo.coefficient,
                        isFree: acceptanceInfo.isFree,
                        isAvailable: true,
                        cell: cell
                    };
                }
                return null;
            }

            const dateText = dateSpan.textContent.trim();
            if (!dateText) return null;

            // Извлекаем информацию о приемке
            const acceptanceInfo = this.extractAcceptanceInfo(cell);
            
            // Проверяем доступность по наличию данных о приемке
            const isAvailable = acceptanceInfo.text !== 'Неизвестно' && 
                               acceptanceInfo.text !== 'Пока недоступно' &&
                               !cellText.includes('недоступно');

            if (!isAvailable) {
                console.log(`   ⚠️ Пропускаем "${dateText}": недоступна для бронирования`);
                return null;
            }

            // Парсим дату
            const parsedDate = this.parseRussianDate(dateText);

            return {
                dateText: dateText,
                parsedDate: parsedDate,
                acceptance: acceptanceInfo.text,
                coefficient: acceptanceInfo.coefficient,
                isFree: acceptanceInfo.isFree,
                isAvailable: isAvailable,
                cell: cell
            };
        } catch (error) {
            console.warn('Ошибка извлечения данных из ячейки:', error);
            return null;
        }
    }

    extractAcceptanceInfo(cell) {
        try {
            // Получаем весь текст ячейки
            const fullText = cell.textContent;
            
            // Проверка на недоступность
            if (fullText.includes('Пока недоступно') || 
                fullText.includes('недоступно') ||
                fullText.includes('Недоступно')) {
                return { text: 'Пока недоступно', coefficient: 0, isFree: false };
            }
            
            // Ищем "Приемка" и текст после нее
            const priemkaMatch = fullText.match(/Приемка[\s\n]*([^\n]+)/i);
            
            if (!priemkaMatch) {
                // Проверяем весь текст на наличие коэффициента или "Бесплатно"
                if (fullText.includes('Бесплатно') || fullText.includes('бесплатно')) {
                    return { text: 'Бесплатно', coefficient: 0, isFree: true };
                }
                
                const coefMatch = fullText.match(/(\d+(\.\d+)?)\s*x/i);
                if (coefMatch) {
                    return {
                        text: coefMatch[0],
                        coefficient: parseFloat(coefMatch[1]),
                        isFree: false
                    };
                }
                
                return { text: 'Неизвестно', coefficient: 0, isFree: false };
            }

            const acceptanceText = priemkaMatch[1].trim();
            
            // Проверяем на "Бесплатно"
            if (acceptanceText.includes('Бесплатно') || acceptanceText.includes('бесплатно')) {
                return { text: 'Бесплатно', coefficient: 0, isFree: true };
            }

            // Извлекаем числовой коэффициент (например "5x", "10x")
            const coefMatch = acceptanceText.match(/(\d+(\.\d+)?)\s*x/i);
            if (coefMatch) {
                return { 
                    text: acceptanceText, 
                    coefficient: parseFloat(coefMatch[1]), 
                    isFree: false 
                };
            }

            // Проверяем процент (например "75%")
            const percentMatch = acceptanceText.match(/(\d+)\s*%/);
            if (percentMatch) {
                // Конвертируем процент в коэффициент (75% = 0.75)
                const percent = parseInt(percentMatch[1]);
                return {
                    text: acceptanceText,
                    coefficient: percent / 100,
                    isFree: false
                };
            }

            return { text: acceptanceText, coefficient: 0, isFree: false };
        } catch (error) {
            console.warn('Ошибка извлечения приемки:', error);
            return { text: 'Неизвестно', coefficient: 0, isFree: false };
        }
    }

    parseRussianDate(dateStr) {
        try {
            // Формат: "13 октября, пн"
            const months = {
                'января': 0, 'февраля': 1, 'марта': 2, 'апреля': 3,
                'мая': 4, 'июня': 5, 'июля': 6, 'августа': 7,
                'сентября': 8, 'октября': 9, 'ноября': 10, 'декабря': 11
            };

            // Убираем лишние символы
            let cleanStr = dateStr.split(',')[0].trim();
            cleanStr = cleanStr.replace(/\s+/g, ' '); // Множественные пробелы в один
            
            const parts = cleanStr.split(' ');
            if (parts.length < 2) {
                console.warn(`Не удалось распарсить дату: "${dateStr}"`);
                return null;
            }

            const day = parseInt(parts[0]);
            const monthName = parts[1].toLowerCase();
            const month = months[monthName];

            if (month === undefined) {
                console.warn(`Неизвестный месяц: "${monthName}"`);
                return null;
            }

            // Определяем год (если месяц меньше текущего, то следующий год)
            const now = new Date();
            let year = now.getFullYear();
            
            // Если дата в прошлом (месяц прошел), берем следующий год
            if (month < now.getMonth() || (month === now.getMonth() && day < now.getDate())) {
                year++;
            }

            const date = new Date(year, month, day, 12, 0, 0, 0); // Полдень для избежания проблем с часовыми поясами

            return date;
        } catch (error) {
            console.warn('Ошибка парсинга даты:', error);
            return null;
        }
    }

    async matchesFilters(dateInfo) {
        if (!this.filters) {
            return true;
        }

        const { dateMode, specificDate, dateFrom, dateTo, filterByCoefficient, 
                coefficientFrom, coefficientTo, allowFree } = this.filters;

        // Проверка даты
        if (dateMode === 'specific' && specificDate) {
            const targetDate = new Date(specificDate);
            const matches = this.isSameDate(dateInfo.parsedDate, targetDate);
            
            if (!matches) {
                return false;
            }
        } else if (dateMode === 'range' && dateFrom && dateTo) {
            const from = new Date(dateFrom);
            const to = new Date(dateTo);
            
            // Сбрасываем время для корректного сравнения
            from.setHours(0, 0, 0, 0);
            to.setHours(23, 59, 59, 999);
            const current = new Date(dateInfo.parsedDate);
            current.setHours(12, 0, 0, 0);
            
            const inRange = current >= from && current <= to;
            
            if (!inRange) {
                return false;
            }
        }

        // Проверка коэффициента
        if (filterByCoefficient) {
            const coef = dateInfo.coefficient;
            
            // Если "Бесплатно" не разрешено и дата бесплатная
            if (dateInfo.isFree) {
                if (!allowFree) {
                    return false;
                } else {
                    return true;
                }
            }

            // Проверка диапазона коэффициентов
            if (coef < coefficientFrom || coef > coefficientTo) {
                return false;
            }
        }

        return true;
    }

    isSameDate(date1, date2) {
        if (!date1 || !date2) {
            return false;
        }
        
        // Приводим обе даты к одному формату (полдень)
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        d1.setHours(12, 0, 0, 0);
        d2.setHours(12, 0, 0, 0);
        
        const same = d1.getDate() === d2.getDate() &&
                     d1.getMonth() === d2.getMonth() &&
                     d1.getFullYear() === d2.getFullYear();
        
        return same;
    }

    async selectDate(cell) {
        try {
            console.log('🖱️ Наводимся на ячейку и выбираем дату...');

            // Наводим курсор на ячейку
            this.simulateHover(cell);
            await this.sleep(400);

            // Ищем кнопку "Выбрать"
            let selectButton = this.findSelectButton(cell);

            if (selectButton) {
                console.log('✅ Кнопка "Выбрать" найдена, кликаем...');
                this.simulateClick(selectButton);
            } else {
                // Кнопка не найдена - кликаем по самой ячейке (это тоже работает!)
                console.log('⚠️ Кнопка "Выбрать" не найдена, кликаем по ячейке напрямую');
                this.simulateClick(cell);
            }
            
            // Даем время на обработку клика
            await this.sleep(500);

            console.log('✅ Клик по дате выполнен!');
            return true;
        } catch (error) {
            console.error('Ошибка при выборе даты:', error);
            return false;
        }
    }

    simulateHover(element) {
        const events = ['mouseover', 'mouseenter', 'mousemove'];
        
        events.forEach(eventType => {
            const event = new MouseEvent(eventType, {
                view: window,
                bubbles: true,
                cancelable: true
            });
            element.dispatchEvent(event);
        });

        // Добавляем подсветку для визуализации
        element.style.outline = '2px solid #10b981';
        setTimeout(() => {
            element.style.outline = '';
        }, 1000);
    }

    findSelectButton(cell) {
        // Быстрый поиск кнопки "Выбрать" среди видимых кнопок
        const allButtons = document.querySelectorAll('button');
        
        for (const btn of allButtons) {
            const text = btn.textContent.toLowerCase().trim();
            if (text === 'выбрать' || text === 'select') {
                // Проверяем, что кнопка видима
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    console.log('   ✅ Найдена кнопка "Выбрать"');
                    return btn;
                }
            }
        }

        return null;
    }

    async waitForElement(selector, timeout = 5000) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < timeout) {
            const element = document.querySelector(selector);
            if (element) {
                return element;
            }
            await this.sleep(100);
        }
        
        return null;
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async clickFinalPlanButton() {
        try {
            console.log('');
            console.log('🔍 ИЩЕМ ФИНАЛЬНУЮ КНОПКУ "ЗАПЛАНИРОВАТЬ"...');
            
            // Ждем, чтобы кнопка стала активной после выбора даты
            await this.sleep(500);
            
            let planButton = null;
            const attempts = 3;
            
            for (let attempt = 1; attempt <= attempts; attempt++) {
                console.log(`   Попытка ${attempt}/${attempts}...`);
                
                // Ищем все кнопки на странице
                const allButtons = document.querySelectorAll('button');
                console.log(`   Найдено кнопок на странице: ${allButtons.length}`);
                
                // Ищем кнопки с текстом "Запланировать"
                const planButtons = [];
                
                for (const btn of allButtons) {
                    const text = btn.textContent.toLowerCase().trim();
                    
                    // Проверяем текст
                    if (text === 'запланировать' || text.includes('запланировать')) {
                        const rect = btn.getBoundingClientRect();
                        
                        // Проверяем видимость
                        if (rect.width > 0 && rect.height > 0) {
                            const classes = btn.className;
                            console.log(`   📍 Кнопка найдена: текст="${text}", классы="${classes}", размер=${rect.width}x${rect.height}`);
                            planButtons.push({ btn, rect, text, classes });
                        }
                    }
                }
                
                console.log(`   Найдено кнопок "Запланировать": ${planButtons.length}`);
                
                if (planButtons.length > 0) {
                    // Берем последнюю (обычно финальная кнопка последняя)
                    planButton = planButtons[planButtons.length - 1].btn;
                    console.log(`   ✅ Выбрана кнопка #${planButtons.length}: "${planButtons[planButtons.length - 1].text}"`);
                    break;
                }
                
                if (attempt < attempts) {
                    console.log(`   ⏳ Кнопка не найдена, ждем ${500}мс...`);
                    await this.sleep(500);
                }
            }

            if (!planButton) {
                console.log('   ❌ Финальная кнопка "Запланировать" не найдена после всех попыток');
                console.log('   Выводим все кнопки на странице для отладки:');
                
                const allButtons = document.querySelectorAll('button');
                Array.from(allButtons).slice(0, 10).forEach((btn, i) => {
                    const text = btn.textContent.trim().substring(0, 50);
                    console.log(`      ${i + 1}. "${text}" - классы: ${btn.className.substring(0, 80)}`);
                });
                
                return false;
            }

            console.log('   ✅ КЛИКАЕМ НА ФИНАЛЬНУЮ "ЗАПЛАНИРОВАТЬ"...');
            
            // Подсвечиваем кнопку
            this.highlightElement(planButton);
            
            // Множественные клики для надежности
            this.simulateClick(planButton);
            await this.sleep(200);
            this.simulateClick(planButton);
            
            console.log('   ✅ Клик выполнен!');
            
            await this.sleep(500);
            
            return true;
        } catch (error) {
            console.error('Ошибка при клике на финальную "Запланировать":', error);
            return false;
        }
    }

    async enterMonopalletCount(count) {
        try {
            console.log('🔍 Ищем поле ввода количества монопаллет...');
            
            // Ищем поле ввода
            const inputSelectors = [
                'input[type="number"]',
                'input[placeholder*="монопаллет"]',
                'input[placeholder*="количество"]',
                'input[class*="input"]'
            ];

            let inputField = null;

            for (const selector of inputSelectors) {
                const inputs = document.querySelectorAll(selector);
                for (const input of inputs) {
                    const rect = input.getBoundingClientRect();
                    // Проверяем видимость
                    if (rect.width > 0 && rect.height > 0) {
                        // Проверяем, что это поле для числа
                        if (input.type === 'number' || input.type === 'text') {
                            inputField = input;
                            console.log(`   ✅ Найдено поле ввода по селектору: ${selector}`);
                            break;
                        }
                    }
                }
                if (inputField) break;
            }

            if (!inputField) {
                console.log('   ❌ Поле ввода не найдено');
                
                // Выводим все input для отладки
                const allInputs = document.querySelectorAll('input');
                console.log('   Все input на странице:');
                Array.from(allInputs).slice(0, 5).forEach((inp, i) => {
                    console.log(`      ${i + 1}. type="${inp.type}", placeholder="${inp.placeholder}", value="${inp.value}"`);
                });
                
                return false;
            }

            console.log(`   ✅ Вводим количество: ${count}`);
            
            // Очищаем поле
            inputField.value = '';
            
            // Фокусируемся на поле
            inputField.focus();
            
            await this.sleep(100);
            
            // Вводим значение
            inputField.value = count.toString();
            
            // Эмулируем события ввода
            inputField.dispatchEvent(new Event('input', { bubbles: true }));
            inputField.dispatchEvent(new Event('change', { bubbles: true }));
            
            // Подсвечиваем поле
            this.highlightElement(inputField);
            
            console.log('   ✅ Количество введено!');
            
            return true;
        } catch (error) {
            console.error('Ошибка при вводе количества монопаллет:', error);
            return false;
        }
    }

    async closeModal() {
        try {
            console.log('');
            console.log('🔄 ЗАКРЫВАЕМ МОДАЛЬНОЕ ОКНО...');
            
            // Сразу жмем ESC - самый надежный способ
            console.log('   ⌨️ Нажимаем ESC...');
            
            // Отправляем события ESC
            const escapeEvent = new KeyboardEvent('keydown', {
                key: 'Escape',
                code: 'Escape',
                keyCode: 27,
                which: 27,
                bubbles: true,
                cancelable: true
            });
            
            document.dispatchEvent(escapeEvent);
            
            // Также пробуем на body и activeElement
            document.body.dispatchEvent(escapeEvent);
            if (document.activeElement) {
                document.activeElement.dispatchEvent(escapeEvent);
            }
            
            // Отправляем keyup тоже
            const escapeUpEvent = new KeyboardEvent('keyup', {
                key: 'Escape',
                code: 'Escape',
                keyCode: 27,
                which: 27,
                bubbles: true,
                cancelable: true
            });
            
            document.dispatchEvent(escapeUpEvent);
            
            await this.sleep(500);
            
            console.log('   ✅ ESC нажат, модалка должна закрыться');
            console.log('═══════════════════════════════════════════');
            console.log('');
            
            return true;
        } catch (error) {
            console.error('Ошибка при закрытии модального окна:', error);
            return false;
        }
    }

    async saveClickStats() {
        try {
            const stats = await chrome.storage.local.get(['autoCatchStats']) || {};
            const currentStats = stats.autoCatchStats || {
                totalClicks: 0,
                successfulClicks: 0,
                lastClickTime: null,
                sessionClicks: 0
            };

            currentStats.totalClicks++;
            currentStats.sessionClicks = this.clickCount;
            currentStats.lastClickTime = this.lastClickTime;

            await chrome.storage.local.set({ autoCatchStats: currentStats });
        } catch (error) {
            console.error('Error saving click stats:', error);
        }
    }

    showPageNotification(message, type = 'info') {
        // Переиспользуем существующий метод, но с доработкой
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background: ${type === 'success' ? 
                'linear-gradient(135deg, #10b981 0%, #059669 100%)' : 
                'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'};
            color: white;
            border-radius: 12px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999999;
            animation: slideInRight 0.3s ease;
        `;
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 20px;">${type === 'success' ? '✅' : '📦'}</span>
                <span>${message}</span>
            </div>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // ============= REDISTRIBUTE METHODS =============

    async startRedistribute(settings = {}) {
        console.log('═══════════════════════════════════════════');
        console.log('🔄 ЗАПУСК ПЕРЕРАСПРЕДЕЛЕНИЯ ОСТАТКОВ');
        console.log('═══════════════════════════════════════════');
        console.log('📋 Полученные настройки:', JSON.stringify(settings, null, 2));
        console.log('   Артикул:', settings.article);
        console.log('   📦 Количество:', settings.quantity);
        console.log('   📤 Откуда:', settings.warehouseFrom);
        console.log('   📥 Куда:', settings.warehouseTo);
        
        if (!settings.article) {
            console.log('❌ АРТИКУЛ НЕ ПЕРЕДАН!');
            this.showPageNotification('❌ Артикул не указан', 'error');
            return { success: false, error: 'No article' };
        }
        
        if (!settings.warehouseFrom || !settings.warehouseTo) {
            console.log('❌ СКЛАДЫ НЕ ВЫБРАНЫ!');
            this.showPageNotification('❌ Выберите склады', 'error');
            return { success: false, error: 'No warehouses' };
        }
        
        console.log('═══════════════════════════════════════════');

        this.redistributeEnabled = true;
        this.redistributeCount = 0;
        this.redistributeSettings = settings;
        
        // Проверяем, что сохранилось
        console.log('✅ Сохранено в this.redistributeSettings:', this.redistributeSettings);

        this.showPageNotification('🔄 Перераспределение запущено!', 'info');

        // Начинаем процесс
        await this.clickRedistributeButton();

        return { success: true, enabled: true };
    }

    stopRedistribute() {
        console.log('🛑 Остановка перераспределения');
        this.redistributeEnabled = false;
        this.showPageNotification('🛑 Перераспределение остановлено', 'info');
    }

    async clickRedistributeButton() {
        try {
            // Сначала обновляем данные
            console.log('🔄 Обновляем данные перед началом цикла...');
            await this.clickRefreshButton();
            
            await this.sleep(1000); // Ждем обновления данных
            
            console.log('🔍 Ищем кнопку "Перераспределить остатки"...');

            // Селекторы кнопки из скриншота
            const selectors = [
                'button.button_FX4vJp8gps.m_qtQ4BenJjw',
                'button[class*="button_FX4vJp8gps"]',
                'button[class*="m_qtQ4BenJjw"]'
            ];

            let redistributeButton = null;

            // Пробуем найти по селекторам
            for (const selector of selectors) {
                redistributeButton = document.querySelector(selector);
                if (redistributeButton) {
                    console.log(`   ✅ Найдена по селектору: ${selector}`);
                    break;
                }
            }

            // Если не найдена, ищем по тексту
            if (!redistributeButton) {
                console.log('   🔍 Ищем по тексту...');
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent.toLowerCase().trim();
                    if (text.includes('перераспределить') && text.includes('остатки')) {
                        redistributeButton = btn;
                        console.log('   ✅ Найдена по тексту "Перераспределить остатки"');
                        break;
                    }
                }
            }

            if (!redistributeButton) {
                console.log('   ❌ Кнопка "Перераспределить остатки" не найдена');
                
                // Выводим все кнопки для отладки
                const allButtons = document.querySelectorAll('button');
                console.log('   Все кнопки на странице:');
                Array.from(allButtons).slice(0, 10).forEach((btn, i) => {
                    const text = btn.textContent.trim().substring(0, 50);
                    console.log(`      ${i + 1}. "${text}" - классы: ${btn.className.substring(0, 80)}`);
                });
                
                return { success: false, reason: 'not_found' };
            }

            // Проверяем доступность кнопки
            if (redistributeButton.disabled || redistributeButton.classList.contains('disabled')) {
                console.log('   ⚠️ Кнопка недоступна');
                return { success: false, reason: 'disabled' };
            }

            console.log('   ✅ Кликаем на "Перераспределить остатки"...');
            
            // Подсвечиваем кнопку
            this.highlightElement(redistributeButton);
            
            // Кликаем
            this.simulateClick(redistributeButton);

            this.redistributeCount++;
            
            console.log('   ✅ Клик выполнен!');
            console.log('═══════════════════════════════════════════');

            // Ждем открытия popup окна
            await this.sleep(500);
            await this.checkForRedistributeModal();

            return { success: true, count: this.redistributeCount };
        } catch (error) {
            console.error('Ошибка при клике на "Перераспределить остатки":', error);
            return { success: false, error: error.message };
        }
    }

    async checkForRedistributeModal() {
        try {
            console.log('🔍 Проверяем, открылось ли модальное окно перераспределения...');
            
            await this.sleep(500);
            
            const modals = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"], [class*="Modal"]');
            
            console.log(`   Найдено модальных окон: ${modals.length}`);
            
            if (modals.length > 0) {
                console.log('✅ Модальное окно перераспределения открылось!');
                this.showPageNotification('✅ Окно открыто, вводим артикул...', 'info');
                
                // Вводим артикул
                await this.sleep(500);
                const inputSuccess = await this.enterArticleInModal();
                
                if (inputSuccess) {
                    console.log('✅ Артикул успешно введен!');
                    this.showPageNotification('✅ Артикул введен!', 'success');
                } else {
                    console.log('⚠️ Не удалось ввести артикул');
                    this.showPageNotification('⚠️ Ошибка ввода артикула', 'warning');
                }
                
                return true;
            } else {
                console.log('⚠️ Модальное окно не найдено');
                return false;
            }
        } catch (error) {
            console.error('Ошибка при проверке модального окна:', error);
            return false;
        }
    }

    async enterArticleInModal() {
        try {
            console.log('');
            console.log('🔍 ВВОД АРТИКУЛА');
            console.log('═══════════════════════════════════════════');
            
            // ПРОВЕРЯЕМ, что артикул есть
            if (!this.redistributeSettings || !this.redistributeSettings.article) {
                console.log('❌ АРТИКУЛ НЕ УСТАНОВЛЕН В redistributeSettings!');
                console.log('   redistributeSettings:', this.redistributeSettings);
                return false;
            }
            
            const article = this.redistributeSettings.article;
            console.log('📝 Артикул для ввода:', article);
            
            // ШАГ 1: Найти и кликнуть на поле с placeholder "Введите артикул WB"
            console.log('');
            console.log('ШАГ 1: Ищем поле с placeholder...');
            
            const firstField = document.querySelector('input[placeholder*="Введите артикул"]');
            
            if (!firstField) {
                console.log('❌ Поле с placeholder не найдено');
                return false;
            }

            console.log(`✅ Поле найдено: "${firstField.placeholder}"`);
            console.log('🖱️ Кликаем на поле...');
            
            firstField.click();
            
            // Ждем появления поля ввода
            await this.sleep(300);

            // ШАГ 2: Найти появившееся поле ввода
            console.log('');
            console.log('ШАГ 2: Ищем появившееся поле ввода...');
            
            const allInputs = document.querySelectorAll('input');
            let inputField = null;
            
            // Ищем поле которое в фокусе или последнее видимое
            for (const inp of allInputs) {
                const rect = inp.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    // Приоритет - полю в фокусе
                    if (document.activeElement === inp) {
                        inputField = inp;
                        console.log('✅ Поле в фокусе найдено');
                        break;
                    }
                    // Или берем последнее
                    inputField = inp;
                }
            }

            if (!inputField) {
                console.log('❌ Поле ввода не появилось');
                return false;
            }

            console.log(`✅ Используем поле: type="${inputField.type}"`);
            
            // Фокусируемся если еще нет
            if (document.activeElement !== inputField) {
                inputField.focus();
            }
            
            await this.sleep(100);

            // Вводим артикул
            console.log('⌨️ Вводим артикул...');
            
            inputField.value = '';
            
            for (let i = 0; i < article.length; i++) {
                const char = article[i];
                inputField.value += char;
                inputField.dispatchEvent(new Event('input', { bubbles: true }));
                await this.sleep(50);
            }

            console.log('✅ ВВЕДЕНО:', inputField.value);
            console.log('═══════════════════════════════════════════');
            
            await this.sleep(500);
            
            // Ждем появления выпадающего списка и кликаем на опцию
            const optionClicked = await this.clickArticleOption();
            
            if (optionClicked) {
                console.log('✅ Опция артикула выбрана!');
                
                // Теперь выбираем склады
                await this.sleep(500);
                await this.selectWarehouses();
                
                return true;
            } else {
                console.log('⚠️ Не удалось выбрать опцию, но артикул введен');
                return true;
            }

        } catch (error) {
            console.error('Ошибка ввода:', error);
            return false;
        }
    }

    async clickArticleOption() {
        try {
            console.log('');
            console.log('🔍 ИЩЕМ ОПЦИЮ АРТИКУЛА В ВЫПАДАЮЩЕМ СПИСКЕ');
            console.log('═══════════════════════════════════════════');
            
            // Ждем появления выпадающего списка (1 секунда)
            console.log('⏳ Ждем 1 секунду перед кликом...');
            await this.sleep(1000);
            
            // Селекторы кнопки из скриншота
            const selectors = [
                'button.dropdown-option__4MPHkS4FN',
                'button[class*="dropdown-option"]',
                'button[class*="Dropdown-option"]',
                'button[class*="Dropdown-option--selected"]'
            ];

            let optionButton = null;

            for (const selector of selectors) {
                const buttons = document.querySelectorAll(selector);
                for (const btn of buttons) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        optionButton = btn;
                        console.log(`✅ Опция найдена по селектору: ${selector}`);
                        console.log(`   Текст: "${btn.textContent.trim().substring(0, 50)}"`);
                        break;
                    }
                }
                if (optionButton) break;
            }

            if (!optionButton) {
                console.log('❌ Опция в выпадающем списке не найдена');
                
                // Выводим все кнопки для отладки
                const allButtons = document.querySelectorAll('button');
                console.log('Все кнопки на странице:');
                Array.from(allButtons).slice(0, 10).forEach((btn, i) => {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        console.log(`   ${i + 1}. "${btn.textContent.trim().substring(0, 40)}" - ${btn.className.substring(0, 60)}`);
                    }
                });
                
                return false;
            }

            console.log('🖱️ Кликаем на опцию...');
            
            // Подсвечиваем
            this.highlightElement(optionButton);
            
            // Кликаем
            this.simulateClick(optionButton);
            
            console.log('✅ Клик на опцию выполнен!');
            console.log('═══════════════════════════════════════════');
            
            await this.sleep(500);

            return true;
        } catch (error) {
            console.error('Ошибка при клике на опцию:', error);
            return false;
        }
    }

    async selectWarehouses() {
        try {
            console.log('');
            console.log('🏭 ВЫБОР СКЛАДОВ');
            console.log('═══════════════════════════════════════════');
            console.log('📤 Откуда забрать:', this.redistributeSettings.warehouseFrom);
            console.log('📥 Куда переместить:', this.redistributeSettings.warehouseTo);
            
            // ШАГ 1: Выбираем склад ОТКУДА забрать
            console.log('');
            console.log('ШАГ 1: Выбираем склад ОТКУДА забрать...');
            const fromSelected = await this.selectWarehouseFrom();
            
            if (!fromSelected) {
                console.log('❌ Не удалось выбрать склад ОТКУДА');
                console.log('🔄 Закрываем popup и начинаем цикл заново...');
                
                // Закрываем popup (ESC дважды)
                await this.closeModalWithEsc();
                
                // Начинаем цикл заново
                if (this.redistributeEnabled) {
                    await this.sleep(1000);
                    await this.clickRedistributeButton();
                }
                
                return false;
            }
            
            await this.sleep(500);
            
            // ШАГ 2: Выбираем склад КУДА переместить
            console.log('');
            console.log('ШАГ 2: Выбираем склад КУДА переместить...');
            const toSelected = await this.selectWarehouseTo();
            
            if (!toSelected) {
                console.log('❌ Не удалось выбрать склад КУДА');
                console.log('🔄 Закрываем popup и начинаем цикл заново...');
                
                // Закрываем popup (ESC дважды)
                await this.closeModalWithEsc();
                
                // Начинаем цикл заново
                if (this.redistributeEnabled) {
                    await this.sleep(1000);
                    await this.clickRedistributeButton();
                }
                
                return false;
            }
            
            console.log('');
            console.log('✅ ОБА СКЛАДА ВЫБРАНЫ!');
            console.log('═══════════════════════════════════════════');
            
            await this.sleep(500);
            
            // ШАГ 3: Вводим количество товара
            console.log('');
            console.log('ШАГ 3: Вводим количество товара...');
            const quantityEntered = await this.enterQuantity();
            
            if (!quantityEntered) {
                console.log('❌ Не удалось ввести количество');
                await this.closeModalWithEsc();
                
                if (this.redistributeEnabled) {
                    await this.sleep(1000);
                    await this.clickRedistributeButton();
                }
                
                return false;
            }
            
            await this.sleep(500);
            
            // ШАГ 4: Нажимаем кнопку "Перераспределить"
            console.log('');
            console.log('ШАГ 4: Нажимаем кнопку "Перераспределить"...');
            const redistributed = await this.clickFinalRedistributeButton();
            
            if (redistributed) {
                console.log('');
                console.log('═══════════════════════════════════════════');
                console.log('🎉 ПЕРЕРАСПРЕДЕЛЕНИЕ ВЫПОЛНЕНО!');
                console.log('   Артикул:', this.redistributeSettings.article);
                console.log('   Количество:', this.redistributeSettings.quantity);
                console.log('   Откуда:', this.redistributeSettings.warehouseFrom);
                console.log('   Куда:', this.redistributeSettings.warehouseTo);
                console.log('═══════════════════════════════════════════');
                
                this.showPageNotification('🎉 Перераспределение выполнено!', 'success');
                
                // Останавливаем
                this.redistributeEnabled = false;
                await chrome.storage.local.set({ redistributeEnabled: false });
                
                chrome.runtime.sendMessage({
                    action: 'redistributeCompleted',
                    settings: this.redistributeSettings
                });
            } else {
                console.log('⚠️ Не удалось нажать кнопку "Перераспределить"');
                await this.closeModalWithEsc();
                
                if (this.redistributeEnabled) {
                    await this.sleep(1000);
                    await this.clickRedistributeButton();
                }
            }
            
            return true;
        } catch (error) {
            console.error('Ошибка при выборе складов:', error);
            return false;
        }
    }

    async selectWarehouseFrom() {
        try {
            console.log('🔍 Ищем поле выбора склада (откуда)...');
            
            // Селектор поля из скриншота
            const fieldSelectors = [
                'input.select__input__xUW6rdo8v',
                'input[class*="select__input"]',
                'input[id="warehouseFrom"]',
                'input[name="warehouseFrom"]',
                'input[placeholder*="Выберите склад"]'
            ];

            let warehouseField = null;

            for (const selector of fieldSelectors) {
                const fields = document.querySelectorAll(selector);
                for (const field of fields) {
                    const rect = field.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        warehouseField = field;
                        console.log(`✅ Поле найдено по селектору: ${selector}`);
                        break;
                    }
                }
                if (warehouseField) break;
            }

            if (!warehouseField) {
                console.log('❌ Поле выбора склада не найдено');
                return false;
            }

            console.log('🖱️ Кликаем на поле...');
            warehouseField.click();
            
            await this.sleep(500);

            // Ищем нужный склад в выпадающем списке
            console.log(`🔍 Ищем "${this.redistributeSettings.warehouseFrom}" в списке...`);
            
            const selected = await this.selectWarehouseFromDropdown(this.redistributeSettings.warehouseFrom);
            
            if (selected) {
                console.log(`✅ Склад ОТКУДА выбран: ${this.redistributeSettings.warehouseFrom}`);
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Ошибка выбора склада ОТКУДА:', error);
            return false;
        }
    }

    async selectWarehouseTo() {
        try {
            console.log('🔍 Ищем второе поле выбора склада (куда)...');
            
            // Ищем все поля "Выберите склад"
            const allFields = document.querySelectorAll('input[placeholder*="Выберите склад"], input[class*="select__input"]');
            
            console.log(`   Найдено полей "Выберите склад": ${allFields.length}`);
            
            let warehouseField = null;
            
            // Берем второе поле (первое уже заполнено)
            if (allFields.length >= 2) {
                warehouseField = allFields[1];
                console.log('   ✅ Взято второе поле');
            } else if (allFields.length === 1) {
                // Если только одно поле, возможно первое уже заполнилось
                warehouseField = allFields[0];
                console.log('   ⚠️ Найдено только одно поле, используем его');
            }

            if (!warehouseField) {
                console.log('   ❌ Второе поле не найдено');
                return false;
            }

            console.log('   🖱️ Кликаем на поле...');
            warehouseField.click();
            
            await this.sleep(500);

            // Ищем нужный склад в выпадающем списке
            console.log(`   🔍 Ищем "${this.redistributeSettings.warehouseTo}" в списке...`);
            
            const selected = await this.selectWarehouseFromDropdown(this.redistributeSettings.warehouseTo);
            
            if (selected) {
                console.log(`   ✅ Склад КУДА выбран: ${this.redistributeSettings.warehouseTo}`);
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Ошибка выбора склада КУДА:', error);
            return false;
        }
    }

    async clickRefreshButton() {
        try {
            console.log('🔍 Ищем кнопку обновления данных...');
            
            // Ищем кнопку с SVG иконкой обновления
            const buttons = document.querySelectorAll('button');
            
            for (const btn of buttons) {
                // Проверяем наличие SVG внутри
                const svg = btn.querySelector('svg');
                if (svg) {
                    // Проверяем path внутри SVG (иконка обновления имеет характерный path)
                    const path = svg.querySelector('path');
                    if (path) {
                        const d = path.getAttribute('d');
                        // Иконка обновления обычно имеет круговой path
                        if (d && (d.includes('M12') || d.includes('rotate') || d.length > 50)) {
                            const rect = btn.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && rect.width < 50 && rect.height < 50) {
                                console.log('✅ Кнопка обновления найдена (по SVG иконке)');
                                
                                // Подсвечиваем
                                this.highlightElement(btn);
                                
                                // Кликаем
                                this.simulateClick(btn);
                                
                                console.log('✅ Клик на обновление выполнен!');
                                
                                return true;
                            }
                        }
                    }
                }
            }

            console.log('⚠️ Кнопка обновления не найдена (не критично, продолжаем)');
            return false;
        } catch (error) {
            console.error('Ошибка клика на обновление:', error);
            return false;
        }
    }

    async closeModalWithEsc() {
        console.log('');
        console.log('⌨️ ЗАКРЫВАЕМ POPUP (ESC x2)');
        
        // Первый ESC
        document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Escape',
            code: 'Escape',
            keyCode: 27,
            which: 27,
            bubbles: true,
            cancelable: true
        }));
        
        await this.sleep(200);
        
        // Второй ESC для надежности
        document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Escape',
            code: 'Escape',
            keyCode: 27,
            which: 27,
            bubbles: true,
            cancelable: true
        }));
        
        document.body.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Escape',
            keyCode: 27,
            bubbles: true
        }));
        
        await this.sleep(500);
        
        console.log('✅ ESC нажат дважды, popup должен закрыться');
        console.log('♻️ Начинаем цикл заново...');
        console.log('');
    }

    async enterQuantity() {
        try {
            console.log('🔍 Ищем поле ввода количества...');
            
            // Селекторы из скриншота
            const quantityField = document.querySelector('input#quantity') || 
                                 document.querySelector('input[name="quantity"]') ||
                                 document.querySelector('input[placeholder*="Укажите кол-во"]') ||
                                 document.querySelector('input.simple-input__field__v6Z2eG-3Xt');
            
            if (!quantityField) {
                console.log('❌ Поле количества не найдено');
                return false;
            }

            console.log(`✅ Поле найдено: placeholder="${quantityField.placeholder}"`);
            console.log(`📝 Вводим количество: ${this.redistributeSettings.quantity}`);
            
            // Кликаем и фокусируемся
            quantityField.click();
            quantityField.focus();
            
            await this.sleep(100);
            
            // Очищаем и вводим количество
            quantityField.value = '';
            
            const quantity = this.redistributeSettings.quantity.toString();
            for (let i = 0; i < quantity.length; i++) {
                const char = quantity[i];
                quantityField.value += char;
                quantityField.dispatchEvent(new Event('input', { bubbles: true }));
                await this.sleep(50);
            }
            
            quantityField.dispatchEvent(new Event('change', { bubbles: true }));
            
            console.log('✅ Количество введено:', quantityField.value);
            
            return true;
        } catch (error) {
            console.error('Ошибка ввода количества:', error);
            return false;
        }
    }

    async clickFinalRedistributeButton() {
        try {
            console.log('🔍 Ищем кнопку "Перераспределить"...');
            
            // Селекторы из скриншота
            const selectors = [
                'button.button__bta9qNQSZI.m__qXnrynn8P',
                'button[class*="button__bta9qNQSZI"]',
                'button[class*="m__qXnrynn8P"]'
            ];

            let redistributeBtn = null;

            for (const selector of selectors) {
                const buttons = document.querySelectorAll(selector);
                for (const btn of buttons) {
                    const text = btn.textContent.toLowerCase().trim();
                    if (text.includes('перераспределить')) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            redistributeBtn = btn;
                            console.log(`✅ Кнопка найдена по селектору: ${selector}`);
                            break;
                        }
                    }
                }
                if (redistributeBtn) break;
            }

            // Если не найдена, ищем по тексту
            if (!redistributeBtn) {
                console.log('🔍 Ищем по тексту...');
                const allButtons = document.querySelectorAll('button');
                for (const btn of allButtons) {
                    const text = btn.textContent.toLowerCase().trim();
                    if (text === 'перераспределить') {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            redistributeBtn = btn;
                            console.log('✅ Кнопка найдена по тексту');
                            break;
                        }
                    }
                }
            }

            if (!redistributeBtn) {
                console.log('❌ Кнопка "Перераспределить" не найдена');
                return false;
            }

            console.log('🖱️ Кликаем на кнопку "Перераспределить"...');
            
            // Подсвечиваем
            this.highlightElement(redistributeBtn);
            
            // Кликаем
            this.simulateClick(redistributeBtn);
            
            await this.sleep(500);
            
            console.log('✅ Клик выполнен!');
            
            return true;
        } catch (error) {
            console.error('Ошибка клика на "Перераспределить":', error);
            return false;
        }
    }

    async selectWarehouseFromDropdown(warehouseName) {
        try {
            console.log(`🔍 Ищем склад "${warehouseName}" в выпадающем списке...`);
            
            // Ищем все li элементы
            const listItems = document.querySelectorAll('li.dropdown-list__item__SO8E19zeqg');
            
            if (listItems.length === 0) {
                console.log('   ⚠️ li элементы не найдены, пробуем общий селектор...');
                const allLi = document.querySelectorAll('li');
                console.log(`   Найдено всего li: ${allLi.length}`);
            } else {
                console.log(`   ✅ Найдено li элементов: ${listItems.length}`);
            }

            const itemsToCheck = listItems.length > 0 ? listItems : document.querySelectorAll('li');
            
            console.log('   📋 Склады в списке:');
            
            // Проходим по каждому li
            for (const li of itemsToCheck) {
                const rect = li.getBoundingClientRect();
                
                // Только видимые
                if (rect.width > 0 && rect.height > 0) {
                    // Ищем button внутри li
                    const button = li.querySelector('button');
                    
                    if (button) {
                        const buttonText = button.textContent.trim();
                        console.log(`      - "${buttonText}"`);
                        
                        // Сравниваем с нужным складом
                        if (buttonText === warehouseName) {
                            console.log(`   ✅ НАЙДЕН: "${buttonText}"`);
                            console.log('   🖱️ Наводимся и кликаем на button...');
                            
                            // Наводимся на li
                            this.simulateHover(li);
                            await this.sleep(100);
                            
                            // Подсвечиваем button
                            this.highlightElement(button);
                            
                            // Кликаем на button
                            this.simulateClick(button);
                            
                            console.log('   ✅ Клик выполнен!');
                            
                            await this.sleep(300);
                            
                            return true;
                        }
                    } else {
                        // Если нет button, проверяем текст самого li
                        const liText = li.textContent.trim();
                        if (liText === warehouseName) {
                            console.log(`   ✅ НАЙДЕН в li: "${liText}"`);
                            this.highlightElement(li);
                            this.simulateClick(li);
                            await this.sleep(300);
                            return true;
                        }
                    }
                }
            }

            console.log(`   ❌ Склад "${warehouseName}" не найден`);
            return false;
        } catch (error) {
            console.error('Ошибка выбора из dropdown:', error);
            return false;
        }
    }
}

// Initialize content script
const wbScript = new WBContentScript();

// Inject quick access button after page load
window.addEventListener('load', () => {
    setTimeout(() => {
        wbScript.injectQuickAccessButton();
    }, 1000);
});


