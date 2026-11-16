"""
CampusFlow - проверка конфликтов броней
Ключевая часть MVP (35 баллов оценки)
"""
from datetime import date, time, datetime
from typing import List, Tuple
from sqlalchemy.orm import Session
from ..models import Booking, BookingStatus


def check_time_overlap(
    start1: time, end1: time,
    start2: time, end2: time
) -> bool:
    """
    Проверка пересечения временных интервалов
    Касание границ (15:00 конец и 15:00 начало) НЕ считается конфликтом
    """
    # Преобразуем в минуты для удобства
    start1_min = start1.hour * 60 + start1.minute
    end1_min = end1.hour * 60 + end1.minute
    start2_min = start2.hour * 60 + start2.minute
    end2_min = end2.hour * 60 + end2.minute
    
    # Проверка пересечения: [start1, end1) и [start2, end2)
    # Конфликт если: start1 < end2 AND start2 < end1
    return start1_min < end2_min and start2_min < end1_min


def find_booking_conflicts(
    db: Session,
    room_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    exclude_booking_id: int = None
) -> List[Booking]:
    """
    Поиск конфликтующих броней для аудитории в указанную дату
    """
    query = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.date == booking_date,
        Booking.status == BookingStatus.ACTIVE
    )
    
    # Исключаем текущую бронь при редактировании
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)
    
    existing_bookings = query.all()
    
    conflicts = []
    for booking in existing_bookings:
        if check_time_overlap(start_time, end_time, booking.start_time, booking.end_time):
            conflicts.append(booking)
    
    return conflicts


def validate_booking_time(start_time: time, end_time: time) -> Tuple[bool, str]:
    """
    Проверка корректности временного интервала
    Возвращает (valid, error_message)
    """
    start_min = start_time.hour * 60 + start_time.minute
    end_min = end_time.hour * 60 + end_time.minute
    
    if start_min >= end_min:
        return False, "Время начала должно быть раньше времени окончания"
    
    if end_min - start_min < 30:
        return False, "Минимальная длительность брони - 30 минут"
    
    if end_min - start_min > 480:  # 8 часов
        return False, "Максимальная длительность брони - 8 часов"
    
    # Рабочие часы: 08:00 - 22:00
    if start_min < 8 * 60 or end_min > 22 * 60:
        return False, "Бронирование доступно с 08:00 до 22:00"
    
    return True, ""
