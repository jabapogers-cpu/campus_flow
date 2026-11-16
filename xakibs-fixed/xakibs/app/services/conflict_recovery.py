"""
CampusFlow - умный выход из конфликта
При 409 система предлагает альтернативы
"""
from datetime import date, time, timedelta, datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Booking, Room, BookingStatus
from .conflicts import check_time_overlap
from .pairs import PAIRS


def find_nearby_free_slots(
    db: Session,
    room_id: int,
    requested_date: date,
    requested_start: time,
    requested_end: time,
    max_results: int = 3
) -> List[Dict[str, Any]]:
    """
    Ближайшие свободные пары в этой же аудитории: сегодня-вчера-завтра относительно запрошенной даты
    """
    requested_min = requested_start.hour * 60 + requested_start.minute
    candidates = []

    for date_delta in [0, 1, -1]:
        check_date = requested_date + timedelta(days=date_delta)
        if check_date < date.today():
            continue
        bookings = db.query(Booking).filter(
            Booking.room_id == room_id,
            Booking.date == check_date,
            Booking.status == BookingStatus.ACTIVE
        ).all()

        for pair_start, pair_end in PAIRS:
            if any(check_time_overlap(pair_start, pair_end, b.start_time, b.end_time) for b in bookings):
                continue
            pair_min = pair_start.hour * 60 + pair_start.minute
            candidates.append({
                "date": check_date.isoformat(),
                "start": pair_start.strftime("%H:%M"),
                "end": pair_end.strftime("%H:%M"),
                "distance": abs(date_delta) * 1000 + abs(pair_min - requested_min)
            })

    candidates.sort(key=lambda x: x["distance"])
    return candidates[:max_results]


def find_similar_rooms(
    db: Session,
    requested_room_id: int,
    requested_date: date,
    requested_start: time,
    requested_end: time,
    max_results: int = 3
) -> List[Dict[str, Any]]:
    """
    Топ-3 похожих аудиторий, свободных в запрошенный слот
    Скоринг по совпадению параметров
    """
    requested_room = db.query(Room).filter(Room.id == requested_room_id).first()
    if not requested_room:
        return []
    
    # Получаем все аудитории
    all_rooms = db.query(Room).filter(Room.id != requested_room_id).all()
    
    scored_rooms = []
    for room in all_rooms:
        # Проверяем, свободна ли в запрошенное время
        conflicts = db.query(Booking).filter(
            Booking.room_id == room.id,
            Booking.date == requested_date,
            Booking.status == BookingStatus.ACTIVE
        ).all()
        
        is_free = True
        for booking in conflicts:
            if check_time_overlap(requested_start, requested_end, booking.start_time, booking.end_time):
                is_free = False
                break
        
        if not is_free:
            continue
        
        # Скоринг по параметрам
        score = 0.0
        
        # Совпадение корпуса (+0.4)
        if room.building == requested_room.building:
            score += 0.4
        
        # Близость вместимости (+0.3)
        capacity_diff = abs(room.capacity - requested_room.capacity)
        if capacity_diff == 0:
            score += 0.3
        elif capacity_diff <= 5:
            score += 0.2
        elif capacity_diff <= 10:
            score += 0.1
        
        # Совпадение оборудования (+0.3)
        requested_equipment = set((requested_room.equipment or "").split(","))
        room_equipment = set((room.equipment or "").split(","))
        if requested_equipment and room_equipment:
            equipment_overlap = len(requested_equipment & room_equipment) / len(requested_equipment)
            score += 0.3 * equipment_overlap
        
        scored_rooms.append({
            "room_id": room.id,
            "room_name": room.name,
            "building": room.building,
            "floor": room.floor,
            "capacity": room.capacity,
            "equipment": (room.equipment or "").split(",") if room.equipment else [],
            "score": round(score, 2),
            "free_at_requested_slot": True
        })
    
    # Сортируем по скорингу
    scored_rooms.sort(key=lambda x: x["score"], reverse=True)
    return scored_rooms[:max_results]


def generate_conflict_alternatives(
    db: Session,
    room_id: int,
    booking_date: date,
    start_time: time,
    end_time: time
) -> Dict[str, Any]:
    """
    Генерация полного ответа с альтернативами при конфликте
    """
    return {
        "nearby_slots": find_nearby_free_slots(db, room_id, booking_date, start_time, end_time),
        "similar_rooms": find_similar_rooms(db, room_id, booking_date, start_time, end_time)
    }
