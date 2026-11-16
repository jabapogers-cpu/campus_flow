"""
CampusFlow - рекомендации аудиторий (бонусная фича)
Топ-3 аудитории по параметрам + скоринг по загрузке
"""
from datetime import date, time, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Room, Booking, BookingStatus


def calculate_room_load(db: Session, room_id: int, days: int = 7) -> float:
    """
    Расчёт загрузки аудитории за последние N дней (0.0 - 1.0)
    """
    start_date = date.today() - timedelta(days=days)
    
    bookings = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.date >= start_date,
        Booking.status == BookingStatus.ACTIVE
    ).all()
    
    if not bookings:
        return 0.0
    
    # Считаем общее количество забронированных часов
    total_minutes = 0
    for booking in bookings:
        start_min = booking.start_time.hour * 60 + booking.start_time.minute
        end_min = booking.end_time.hour * 60 + booking.end_time.minute
        total_minutes += (end_min - start_min)
    
    # Рабочий день: 08:00-22:00 = 14 часов = 840 минут
    available_minutes = days * 840
    load = total_minutes / available_minutes if available_minutes > 0 else 0.0
    
    return min(load, 1.0)


def recommend_rooms(
    db: Session,
    building: Optional[str] = None,
    min_capacity: Optional[int] = None,
    equipment: Optional[List[str]] = None,
    booking_date: Optional[date] = None,
    start_time: Optional[time] = None,
    end_time: Optional[time] = None,
    max_results: int = 3
) -> List[Dict[str, Any]]:
    """
    Рекомендация топ-3 аудиторий с учётом параметров и загрузки
    """
    # Базовый запрос с фильтрами
    query = db.query(Room)
    
    if building:
        query = query.filter(Room.building == building)
    
    if min_capacity:
        query = query.filter(Room.capacity >= min_capacity)
    
    if equipment:
        for eq in equipment:
            query = query.filter(Room.equipment.like(f"%{eq}%"))
    
    rooms = query.all()
    
    scored_rooms = []
    for room in rooms:
        score = 0.0
        
        # Базовый скоринг: чем меньше загрузка, тем выше оценка (+0.5)
        load = calculate_room_load(db, room.id)
        score += (1.0 - load) * 0.5
        
        # Если указан слот, проверяем доступность (+0.3)
        is_available = True
        if booking_date and start_time and end_time:
            from .conflicts import check_time_overlap
            conflicts = db.query(Booking).filter(
                Booking.room_id == room.id,
                Booking.date == booking_date,
                Booking.status == BookingStatus.ACTIVE
            ).all()
            
            for booking in conflicts:
                if check_time_overlap(start_time, end_time, booking.start_time, booking.end_time):
                    is_available = False
                    break
            
            if is_available:
                score += 0.3
        
        # Оптимальная вместимость: не слишком большая (+0.2)
        if min_capacity:
            capacity_ratio = room.capacity / min_capacity
            if 1.0 <= capacity_ratio <= 1.5:
                score += 0.2
            elif 1.5 < capacity_ratio <= 2.0:
                score += 0.1
        
        reasons = []
        if booking_date and start_time and end_time:
            reasons.append("свободна в выбранное время" if is_available else "занята в выбранное время")
        reasons.append(f"загрузка за неделю {round(load * 100)}%")
        if min_capacity:
            reasons.append(f"{room.capacity} мест на {min_capacity}+ чел.")
        scored_rooms.append({
            "id": room.id,
            "room_id": room.id,
            "room_name": room.name,
            "reasons": reasons,
            "name": room.name,
            "building": room.building,
            "floor": room.floor,
            "capacity": room.capacity,
            "equipment": (room.equipment or "").split(",") if room.equipment else [],
            "load_percent": round(load * 100, 1),
            "available": is_available if booking_date else None,
            "score": round(score, 2)
        })
    
    # Сортируем по скорингу
    scored_rooms.sort(key=lambda x: x["score"], reverse=True)
    return scored_rooms[:max_results]
