// CampusFlow - frontend JavaScript
const API_BASE = '/api';
let authToken = null;
let currentUser = null;
let selectedRoom = null;
let selectedSlot = null;
let conflictBookingData = null;

// === Авторизация ===
async function quickLogin(login, password) {
    await handleLoginRequest(login, password);
}

async function handleLogin(event) {
    event.preventDefault();
    const login = document.getElementById('login-input').value;
    const password = document.getElementById('password-input').value;
    await handleLoginRequest(login, password);
}

async function handleLoginRequest(login, password) {
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({login, password})
        });
        
        if (!response.ok) {
            throw new Error('Неверный логин или пароль');
        }
        
        const data = await response.json();
        authToken = data.access_token;
        currentUser = data.user;
        
        // Переход на главный экран
        document.getElementById('login-screen').classList.remove('active');
        document.getElementById('main-screen').classList.add('active');
        document.getElementById('user-name').textContent = currentUser.display_name;
        
        // Показываем админку если админ
        if (currentUser.role === 'admin') {
            document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
        }
        
        // Устанавливаем завтрашнюю дату по умолчанию
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        document.getElementById('filter-date').value = localISO(tomorrow);
        
        // Загружаем данные
        await searchRooms();
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
        document.getElementById('login-error').classList.remove('hidden');
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    document.getElementById('main-screen').classList.remove('active');
    document.getElementById('login-screen').classList.add('active');
    document.querySelectorAll('.admin-only').forEach(el => el.classList.add('hidden'));
}

// === Навигация ===
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const viewName = link.dataset.view;
            switchView(viewName);
        });
    });
    
    // Табы админки
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchAdminTab(tabName);
        });
    });
});

function switchView(viewName) {
    // Убираем active со всех видов
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    
    // Активируем нужный
    document.getElementById(`view-${viewName}`).classList.add('active');
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');
    
    // Загружаем данные
    if (viewName === 'bookings') {
        loadMyBookings();
    } else if (viewName === 'waitlist') {
        loadMyWaitlist();
    } else if (viewName === 'admin') {
        loadAdminBookings();
        loadStatsData();
    }
}

function switchAdminTab(tabName) {
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(`admin-${tabName}`).classList.add('active');
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    if (tabName === 'rooms-mgmt') {
        loadAdminRooms();
    } else if (tabName === 'stats') {
        loadStatsData();
    }
}

// === API запросы ===
async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        logout();
        throw new Error('Сессия истекла');
    }
    
    return response;
}

// === Поиск аудиторий ===
async function searchRooms() {
    const building = document.getElementById('filter-building').value;
    const minCapacity = document.getElementById('filter-capacity').value;
    const equipment = getSelectedEquipment();
    
    const params = new URLSearchParams();
    if (building) params.append('building', building);
    if (minCapacity) params.append('minCapacity', minCapacity);
    if (equipment) params.append('equipment', equipment);
    
    try {
        const response = await apiRequest(`/rooms?${params}`);
        const rooms = await response.json();
        displayRooms(rooms);
    } catch (error) {
        console.error('Ошибка загрузки аудиторий:', error);
    }
}

const EQUIP_LABELS = {
    projector: '📽 Проектор', whiteboard: '🖊 Доска', computers: '💻 Компьютеры', smartboard: '🖥 Интерактивная доска'
};

function getSelectedEquipment() {
    return Array.from(document.querySelectorAll('#filter-equipment input:checked')).map(c => c.value).join(',');
}

function equipmentTags(list) {
    return (list || []).filter(Boolean).map(eq => `<span class="equipment-tag">${EQUIP_LABELS[eq.trim()] || eq.trim()}</span>`).join('');
}

function displayRooms(rooms) {
    const grid = document.getElementById('rooms-grid');

    if (rooms.length === 0) {
        grid.innerHTML = '<p style="color: #9CA3AF;">Аудитории не найдены. Попробуйте убрать часть фильтров.</p>';
        return;
    }

    grid.innerHTML = rooms.map(room => `
        <div class="room-card" onclick="openRoomSlots(${room.id})">
            <h3>${room.name}</h3>
            <div class="room-meta">
                <div>📍 Корпус ${room.building}, ${room.floor} этаж</div>
                <div>👥 ${room.capacity} мест</div>
            </div>
            ${room.equipment.length > 0 ? `<div class="room-equipment">${equipmentTags(room.equipment)}</div>` : ''}
        </div>
    `).join('');
}

// === Рекомендации ===
async function getRecommendations() {
    const building = document.getElementById('filter-building').value;
    const minCapacity = document.getElementById('filter-capacity').value;
    const equipment = getSelectedEquipment();
    const date = document.getElementById('filter-date').value;
    const start = document.getElementById('filter-start').value;
    const end = document.getElementById('filter-end').value;

    const params = new URLSearchParams();
    if (building) params.append('building', building);
    if (minCapacity) params.append('minCapacity', minCapacity);
    if (equipment) params.append('equipment', equipment);
    if (date) params.append('date', date);
    if (date && start && end) { params.append('startTime', start); params.append('endTime', end); }

    try {
        const response = await apiRequest(`/rooms/recommend/top?${params}`);
        if (!response.ok) throw new Error('Не удалось получить рекомендации');
        displayRecommendations(await response.json(), Boolean(date && start && end));
    } catch (error) {
        console.error('Ошибка получения рекомендаций:', error);
        alert(error.message);
    }
}

function displayRecommendations(recs, withTime) {
    const grid = document.getElementById('rooms-grid');
    if (!recs.length) {
        grid.innerHTML = '<p style="color: #9CA3AF;">Под эти условия рекомендаций нет. Смягчите фильтры.</p>';
        return;
    }
    const hint = withTime ? '' : ' Укажите дату и время «с / до» — и подбор учтёт, какие аудитории свободны именно тогда.';
    grid.innerHTML = `<div class="rec-title">Топ-${recs.length} аудиторий под ваши условия.${hint}</div>` + recs.map((rec, i) => {
        const id = rec.id ?? rec.room_id;
        const name = rec.name ?? rec.room_name ?? `Аудитория #${id}`;
        const equipment = Array.isArray(rec.equipment) ? rec.equipment : [];
        const status = rec.available === true ? '<span class="rec-badge ok">свободна в это время</span>'
            : rec.available === false ? '<span class="rec-badge busy">занята в это время</span>' : '';
        return `
        <div class="room-card rec-card" onclick="openRoomSlots(${id})">
            <div class="rec-rank">${i + 1}</div>
            <h3>${name}</h3>
            <div class="room-meta">
                <div>📍 Корпус ${rec.building}, ${rec.floor} этаж</div>
                <div>👥 ${rec.capacity} мест</div>
            </div>
            ${equipment.length ? `<div class="room-equipment">${equipmentTags(equipment)}</div>` : ''}
            <div class="rec-score" title="Оценка ${Math.round(rec.score * 100)} из 100"><i style="width:${Math.min(100, Math.round(rec.score * 100))}%"></i></div>
            <div class="rec-meta">Загрузка за неделю: ${rec.load_percent ?? 0}% ${status}</div>
            ${(rec.reasons || []).length ? `<ul class="rec-reasons">${rec.reasons.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
        </div>`;
    }).join('');
}

// === Слоты аудитории ===
async function openRoomSlots(roomId) {
    selectedRoom = roomId;
    const dateStr = document.getElementById('filter-date').value;
    
    if (!dateStr) {
        alert('Выберите дату');
        return;
    }
    
    try {
        // Загружаем информацию об аудитории
        const roomResponse = await apiRequest(`/rooms/${roomId}`);
        const room = await roomResponse.json();
        
        // Загружаем свободные слоты
        const slotsResponse = await apiRequest(`/rooms/${roomId}/free-slots?date=${dateStr}`);
        const freeSlots = await slotsResponse.json();
        
        // Отображаем
        document.getElementById('modal-room-name').textContent = room.name;
        document.getElementById('modal-room-info').innerHTML = `
            <div style="display: flex; gap: 1rem; margin-bottom: 1rem; font-size: 0.9rem; color: #9CA3AF;">
                <span>📍 Корпус ${room.building}, ${room.floor} этаж</span>
                <span>👥 ${room.capacity} мест</span>
            </div>
        `;
        
        selectedSlot = null;
        document.getElementById('booking-form').classList.add('hidden');
        displaySlots(freeSlots);
        document.getElementById('slots-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Ошибка загрузки слотов:', error);
    }
}

// Сетка пар (зеркалит app/services/pairs.py): 80 минут + перемена 10 минут
const PAIRS = [['08:00', '09:20'], ['09:30', '10:50'], ['11:00', '12:20'], ['12:30', '13:50'],
    ['14:00', '15:20'], ['15:30', '16:50'], ['17:00', '18:20'], ['18:30', '19:50'], ['20:00', '21:20']];

function localISO(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

async function errorText(response, fallback) {
    try {
        const data = await response.json();
        const detail = data.detail;
        if (typeof detail === 'string') return detail;
        if (detail && detail.message) return detail.message;
        if (Array.isArray(detail)) return detail.map(d => d.msg).join('; ');
    } catch (e) { /* пустое тело */ }
    return fallback;
}

function displaySlots(freeSlots) {
    const grid = document.getElementById('slots-grid');
    grid.innerHTML = PAIRS.map(([start, end], i) => {
        const free = freeSlots.some(slot => slot.start === start && slot.end === end);
        return `
        <button class="slot-btn pair ${free ? 'free' : 'occupied'}"
                onclick="selectSlot(this, '${start}', '${end}', ${free})">
            <small>${i + 1} пара</small>
            <b>${start}–${end}</b>
            <small>${free ? 'свободно' : 'занято: встать в очередь'}</small>
        </button>`;
    }).join('');
}

function selectSlot(btn, start, end, free) {
    selectedSlot = {start, end, free};

    document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');

    document.getElementById('booking-form').classList.remove('hidden');
    document.getElementById('book-btn').classList.toggle('hidden', !free);
    document.getElementById('waitlist-btn').classList.toggle('hidden', free);
    document.getElementById('slot-hint').textContent = free
        ? `Пара ${start}–${end} свободна.`
        : `Пара ${start}–${end} занята. Встаньте в очередь: если бронь отменят, аудитория достанется вам автоматически.`;
}

function closeModal() {
    document.getElementById('slots-modal').classList.add('hidden');
    selectedRoom = null;
    selectedSlot = null;
    document.getElementById('booking-form').classList.add('hidden');
    document.getElementById('booking-comment').value = '';
}

// === Бронирование ===
async function confirmBooking() {
    if (!selectedRoom || !selectedSlot) {
        alert('Выберите пару');
        return;
    }
    if (!selectedSlot.free) {
        alert('Эта пара занята: нажмите «Встать в очередь»');
        return;
    }
    
    const dateStr = document.getElementById('filter-date').value;
    const comment = document.getElementById('booking-comment').value;
    
    const payload = {
        room_id: selectedRoom,
        date: dateStr,
        start_time: selectedSlot.start,
        end_time: selectedSlot.end,
        comment
    };
    
    try {
        const response = await apiRequest('/bookings', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        if (response.status === 409) {
            // Конфликт - показываем альтернативы
            const conflict = await response.json();
            showConflictModal(conflict.detail, payload);
            return;
        }
        
        if (!response.ok) {
            throw new Error('Ошибка бронирования');
        }
        
        alert('Аудитория успешно забронирована!');
        closeModal();
        await searchRooms(); // Обновляем список
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// === Конфликт и альтернативы ===
function showConflictModal(conflictData, originalBooking) {
    conflictBookingData = originalBooking;
    
    document.getElementById('conflict-message').textContent = conflictData.message;
    
    // Ближайшие слоты
    const nearbySlotsHtml = conflictData.alternatives.nearby_slots.map(slot => `
        <div class="alt-item">
            ${slot.date} | ${slot.start} - ${slot.end}
            <button class="btn-secondary" onclick="bookAlternativeSlot('${slot.date}', '${slot.start}', '${slot.end}')">
                Забронировать
            </button>
        </div>
    `).join('') || '<p style="color: #6B7280;">Нет свободных слотов рядом</p>';
    
    document.getElementById('nearby-slots').innerHTML = nearbySlotsHtml;
    
    // Похожие аудитории
    const similarRoomsHtml = conflictData.alternatives.similar_rooms.map(room => `
        <div class="alt-item">
            <strong>${room.room_name}</strong> (Корпус ${room.building}, ${room.capacity} мест)
            <button class="btn-secondary" onclick="openRoomSlots(${room.room_id})">
                Посмотреть слоты
            </button>
        </div>
    `).join('') || '<p style="color: #6B7280;">Нет похожих аудиторий</p>';
    
    document.getElementById('similar-rooms').innerHTML = similarRoomsHtml;
    
    closeModal();
    document.getElementById('conflict-modal').classList.remove('hidden');
}

function closeConflictModal() {
    document.getElementById('conflict-modal').classList.add('hidden');
    conflictBookingData = null;
}

async function bookAlternativeSlot(date, start, end) {
    const payload = {
        room_id: conflictBookingData.room_id,
        date,
        start_time: start,
        end_time: end,
        comment: conflictBookingData.comment
    };
    
    try {
        const response = await apiRequest('/bookings', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error('Ошибка бронирования');
        }
        
        alert('Альтернативный слот успешно забронирован!');
        closeConflictModal();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

async function joinWaitlist() {
    if (!conflictBookingData) return;
    
    try {
        const response = await apiRequest('/bookings/waitlist', {
            method: 'POST',
            body: JSON.stringify(conflictBookingData)
        });
        
        if (!response.ok) {
            throw new Error('Ошибка добавления в очередь');
        }
        
        alert('Вы добавлены в очередь! Мы уведомим вас, если слот освободится.');
        closeConflictModal();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

async function joinWaitlistFromSlot() {
    if (!selectedRoom || !selectedSlot) {
        alert('Выберите занятую пару');
        return;
    }
    const payload = {
        room_id: selectedRoom,
        date: document.getElementById('filter-date').value,
        start_time: selectedSlot.start,
        end_time: selectedSlot.end,
        comment: document.getElementById('booking-comment').value
    };
    try {
        const response = await apiRequest('/bookings/waitlist', {method: 'POST', body: JSON.stringify(payload)});
        if (!response.ok) throw new Error(await errorText(response, 'Не удалось встать в очередь'));
        alert('Вы в очереди! Если бронь отменят, аудитория достанется вам автоматически. Очередь: раздел «Очередь».');
        closeModal();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// === Мои брони ===
async function loadMyBookings() {
    try {
        const response = await apiRequest('/bookings/my');
        const bookings = await response.json();
        displayBookings(bookings, 'bookings-list');
    } catch (error) {
        console.error('Ошибка загрузки броней:', error);
    }
}

function displayBookings(bookings, containerId) {
    const container = document.getElementById(containerId);
    
    if (bookings.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF;">Нет броней</p>';
        return;
    }
    
    container.innerHTML = bookings.map(booking => `
        <div class="booking-item">
            <div class="booking-info">
                <h4>${booking.room_name}</h4>
                <div class="booking-meta">
                    📅 ${booking.date} | ⏰ ${booking.start_time} - ${booking.end_time}
                    ${booking.comment ? `<br>💬 ${booking.comment}` : ''}
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
                <span class="status-badge ${booking.status}">${booking.status === 'active' ? 'Активна' : 'Отменена'}</span>
                ${booking.status === 'active' ? `
                    <button class="btn-danger" onclick="cancelBooking(${booking.id})">Отменить</button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

async function cancelBooking(bookingId) {
    if (!confirm('Вы уверены, что хотите отменить бронь?')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/bookings/${bookingId}`, {method: 'DELETE'});
        
        if (!response.ok) {
            const error = await response.json();
            if (error.detail === 'FORBIDDEN') {
                alert('Вы не можете отменить чужую бронь');
            } else {
                throw new Error('Ошибка отмены');
            }
            return;
        }
        
        alert('Бронь отменена');
        await loadMyBookings();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// === Очередь ===
async function loadMyWaitlist() {
    try {
        const response = await apiRequest('/bookings/waitlist/my');
        const waitlist = await response.json();
        displayWaitlist(waitlist);
    } catch (error) {
        console.error('Ошибка загрузки очереди:', error);
    }
}

function displayWaitlist(waitlist) {
    const container = document.getElementById('waitlist-list');
    
    if (waitlist.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF;">Вы не стоите в очереди</p>';
        return;
    }
    
    container.innerHTML = waitlist.map(entry => `
        <div class="booking-item">
            <div class="booking-info">
                <h4>${entry.room_name}</h4>
                <div class="booking-meta">
                    📅 ${entry.date} | ⏰ ${entry.start_time} - ${entry.end_time}
                    ${entry.notified ? '<br>✅ Вы были уведомлены о освобождении' : ''}
                </div>
            </div>
        </div>
    `).join('');
}

// === Админка ===
async function loadAdminBookings() {
    const building = document.getElementById('admin-filter-building')?.value || '';
    const dateFrom = document.getElementById('admin-filter-from')?.value || '';
    const dateTo = document.getElementById('admin-filter-to')?.value || '';
    
    const params = new URLSearchParams();
    if (building) params.append('building', building);
    if (dateFrom) params.append('dateFrom', dateFrom);
    if (dateTo) params.append('dateTo', dateTo);
    
    try {
        const response = await apiRequest(`/admin/bookings?${params}`);
        const bookings = await response.json();
        displayAdminBookings(bookings);
    } catch (error) {
        console.error('Ошибка загрузки броней:', error);
    }
}

function displayAdminBookings(bookings) {
    const container = document.getElementById('admin-bookings-list');
    
    if (bookings.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF;">Нет броней</p>';
        return;
    }
    
    container.innerHTML = bookings.map(booking => `
        <div class="booking-item">
            <div class="booking-info">
                <h4>${booking.room_name}</h4>
                <div class="booking-meta">
                    👤 ${booking.user_name} | 📅 ${booking.date} | ⏰ ${booking.start_time} - ${booking.end_time}
                    ${booking.comment ? `<br>💬 ${booking.comment}` : ''}
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
                <span class="status-badge ${booking.status}">${booking.status === 'active' ? 'Активна' : 'Отменена'}</span>
                ${booking.status === 'active' ? `
                    <button class="btn-danger" onclick="adminCancelBooking(${booking.id})">Отменить</button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

async function adminCancelBooking(bookingId) {
    if (!confirm('Отменить эту бронь?')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/admin/bookings/${bookingId}`, {method: 'DELETE'});
        if (!response.ok) throw new Error('Ошибка отмены');
        alert('Бронь отменена');
        await loadAdminBookings();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

async function exportCSV() {
    const dateFrom = document.getElementById('admin-filter-from')?.value || '';
    const dateTo = document.getElementById('admin-filter-to')?.value || '';
    
    const params = new URLSearchParams();
    if (dateFrom) params.append('dateFrom', dateFrom);
    if (dateTo) params.append('dateTo', dateTo);
    
    try {
        const response = await apiRequest(`/admin/export/bookings.csv?${params}`);
        if (!response.ok) throw new Error('Ошибка экспорта');
        const url = URL.createObjectURL(await response.blob());
        const a = document.createElement('a');
        a.href = url;
        a.download = 'bookings.csv';
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        alert('Ошибка экспорта: ' + error.message);
    }
}

async function loadAdminRooms() {
    try {
        const response = await apiRequest('/rooms');
        const rooms = await response.json();
        displayAdminRooms(rooms);
    } catch (error) {
        console.error('Ошибка загрузки аудиторий:', error);
    }
}

function displayAdminRooms(rooms) {
    const container = document.getElementById('admin-rooms-list');
    
    container.innerHTML = rooms.map(room => `
        <div class="room-card">
            <h3>${room.name}</h3>
            <div class="room-meta">
                <div>📍 Корпус ${room.building}, ${room.floor} этаж</div>
                <div>👥 ${room.capacity} мест</div>
            </div>
            ${room.equipment.length > 0 ? `<div class="room-equipment">${equipmentTags(room.equipment)}</div>` : ''}
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                <button class="btn-secondary" onclick="editRoom(${room.id})">Редактировать</button>
                <button class="btn-danger" onclick="deleteRoom(${room.id})">Удалить</button>
            </div>
        </div>
    `).join('');
}

function openRoomModal(room) {
    document.getElementById('room-modal-title').textContent = room ? `Изменить ${room.name}` : 'Новая аудитория';
    document.getElementById('rf-id').value = room ? room.id : '';
    document.getElementById('rf-name').value = room ? room.name : '';
    document.getElementById('rf-building').value = room ? room.building : '';
    document.getElementById('rf-floor').value = room ? room.floor : 1;
    document.getElementById('rf-capacity').value = room ? room.capacity : '';
    const eq = room ? room.equipment.map(e => e.trim()) : [];
    document.querySelectorAll('#rf-equipment input').forEach(c => { c.checked = eq.includes(c.value); });
    document.getElementById('room-modal').classList.remove('hidden');
    document.getElementById('rf-name').focus();
}

function showAddRoomForm() {
    openRoomModal(null);
}

async function editRoom(roomId) {
    try {
        const response = await apiRequest(`/rooms/${roomId}`);
        if (!response.ok) throw new Error('Аудитория не найдена');
        openRoomModal(await response.json());
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

function closeRoomModal() {
    document.getElementById('room-modal').classList.add('hidden');
}

async function submitRoomForm(event) {
    event.preventDefault();
    const id = document.getElementById('rf-id').value;
    const payload = {
        name: document.getElementById('rf-name').value.trim(),
        building: document.getElementById('rf-building').value.trim().toUpperCase(),
        floor: parseInt(document.getElementById('rf-floor').value, 10),
        capacity: parseInt(document.getElementById('rf-capacity').value, 10),
        equipment: Array.from(document.querySelectorAll('#rf-equipment input:checked')).map(c => c.value).join(',')
    };
    try {
        const response = await apiRequest(id ? `/admin/rooms/${id}` : '/admin/rooms', {
            method: id ? 'PUT' : 'POST',
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(await errorText(response, 'Не удалось сохранить аудиторию'));
        closeRoomModal();
        await loadAdminRooms();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

async function deleteRoom(roomId) {
    if (!confirm('Удалить аудиторию?')) return;
    
    try {
        const response = await apiRequest(`/admin/rooms/${roomId}`, {method: 'DELETE'});
        if (!response.ok) {
            const error = await response.json();
            alert(error.detail);
            return;
        }
        alert('Аудитория удалена');
        await loadAdminRooms();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// === Статистика ===
const STATS_QUERY = 'days=3&ahead=7';

async function fetchJson(endpoint) {
    const response = await apiRequest(endpoint);
    if (!response.ok) throw new Error(await errorText(response, `Ошибка ${response.status}`));
    return response.json();
}

async function renderStats(containerId, endpoint, render) {
    const container = document.getElementById(containerId);
    try {
        container.innerHTML = render(await fetchJson(endpoint));
    } catch (error) {
        console.error('Ошибка статистики:', endpoint, error);
        container.innerHTML = `<p style="color: var(--accent-error);">Не удалось загрузить: ${error.message}</p>`;
    }
}

function loadStatsData() {
    renderStats('stats-summary', '/admin/stats/summary', statsSummaryHtml);
    renderStats('stats-heatmap', `/admin/stats/heatmap?${STATS_QUERY}`, statsHeatmapHtml);
    renderStats('stats-buildings', `/admin/stats/by-buildings?${STATS_QUERY}`, statsBuildingsHtml);
    renderStats('stats-days', `/admin/stats/by-days?${STATS_QUERY}`, statsDaysHtml);
    renderStats('stats-top-rooms', `/admin/stats/top-rooms?${STATS_QUERY}&limit=5`, statsTopRoomsHtml);
}

function statsSummaryHtml(summary) {
    return `
        <div class="stat-card"><div class="stat-value">${summary.total_rooms}</div><div class="stat-label">Всего аудиторий</div></div>
        <div class="stat-card"><div class="stat-value">${summary.active_bookings}</div><div class="stat-label">Активных броней впереди</div></div>
        <div class="stat-card"><div class="stat-value">${summary.week_bookings}</div><div class="stat-label">Броней на ближайшие 7 дней</div></div>
        <div class="stat-card"><div class="stat-value">${summary.total_users}</div><div class="stat-label">Пользователей</div></div>`;
}

function statsHeatmapHtml(data) {
    const cell = {};
    data.cells.forEach(c => { cell[c.building + c.date] = c.load_percent; });
    const max = Math.max(10, ...data.cells.map(c => c.load_percent));
    let html = '<h3>Тепловая карта: корпус × день</h3>';
    html += `<div class="heatmap" style="grid-template-columns: 90px repeat(${data.days.length}, minmax(44px, 1fr));"><div></div>` +
        data.days.map(d => `<div class="heat-h">${d.slice(5)}</div>`).join('');
    data.buildings.forEach(b => {
        html += `<div class="heat-l">Корпус ${b}</div>` + data.days.map(d => {
            const v = cell[b + d] || 0;
            const alpha = (0.08 + Math.min(1, v / max) * 0.82).toFixed(2);
            return `<div class="heat-c" style="background: rgba(56, 189, 248, ${alpha}); color: ${v / max > 0.5 ? '#04121c' : '#E5E7EB'};" title="Корпус ${b}, ${d}: ${v}%">${v}%</div>`;
        }).join('');
    });
    return html + '</div><p class="stats-note">Доля занятых часов от 08:00 до 22:00. Период: 3 дня назад и 7 дней вперёд.</p>';
}

function statsBuildingsHtml(data) {
    return '<h3>Загрузка по корпусам</h3>' + data.map(item => `
        <div style="margin: 1rem 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span>Корпус ${item.building} (${item.rooms_count} ауд.)</span>
                <span style="color: var(--accent-primary);">${item.load_percent}%</span>
            </div>
            <div style="background: var(--surface-3); height: 8px; border-radius: 4px; overflow: hidden;">
                <div style="background: var(--accent-primary); height: 100%; width: ${item.load_percent}%;"></div>
            </div>
            <div style="font-size: 0.8rem; color: #9CA3AF; margin-top: 0.25rem;">${item.bookings_count} броней, ${item.hours} ч</div>
        </div>`).join('');
}

function statsDaysHtml(data) {
    return '<h3>Загрузка по дням</h3>' + data.map(item => `
        <div style="margin: 0.8rem 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.4rem;">
                <span>${item.date}</span>
                <span style="color: var(--accent-secondary);">${item.load_percent}% · ${item.bookings_count} броней</span>
            </div>
            <div style="background: var(--surface-3); height: 6px; border-radius: 3px; overflow: hidden;">
                <div style="background: var(--accent-secondary); height: 100%; width: ${item.load_percent}%;"></div>
            </div>
        </div>`).join('');
}

function statsTopRoomsHtml(data) {
    if (!data.length) return '<h3>Топ-5 загруженных аудиторий</h3><p style="color: #9CA3AF;">Пока нет броней за период</p>';
    return '<h3>Топ-5 загруженных аудиторий</h3>' + data.map((item, idx) => `
        <div style="display: flex; justify-content: space-between; padding: 0.75rem; background: var(--surface-3); border-radius: 8px; margin: 0.5rem 0;">
            <div><strong>${idx + 1}. ${item.room_name}</strong><span style="color: #9CA3AF;"> (Корпус ${item.building})</span></div>
            <div style="color: var(--accent-primary);">${item.bookings_count} броней · ${item.hours} ч</div>
        </div>`).join('');
}

// === Живой поиск: фильтры применяются сразу ===
document.addEventListener('DOMContentLoaded', () => {
    let timer;
    const run = () => { if (authToken) searchRooms(); };
    ['filter-building', 'filter-date'].forEach(id => document.getElementById(id).addEventListener('change', run));
    document.getElementById('filter-equipment').addEventListener('change', run);
    document.getElementById('filter-capacity').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 300); });
});
