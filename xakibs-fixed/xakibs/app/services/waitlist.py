"""
CampusFlow - очередь ожидания: при освобождении слота первый в очереди получает бронь автоматически
"""
import time
from datetime import date
from sqlalchemy.orm import Session
from ..models import Booking, BookingStatus, WaitlistEntry
from .conflicts import find_booking_conflicts


def promote_waitlist(db: Session, room_id: int, booking_date: date) -> int:
    """Превращает ожидающие записи в реальные брони, если их интервал теперь свободен. Возвращает число выдач."""
    entries = db.query(WaitlistEntry).filter(
        WaitlistEntry.room_id == room_id,
        WaitlistEntry.date == booking_date,
        WaitlistEntry.notified == 0
    ).order_by(WaitlistEntry.created_at, WaitlistEntry.id).all()

    promoted = 0
    for entry in entries:
        if find_booking_conflicts(db, room_id, booking_date, entry.start_time, entry.end_time):
            continue
        db.add(Booking(
            room_id=room_id, user_id=entry.user_id, date=booking_date,
            start_time=entry.start_time, end_time=entry.end_time,
            status=BookingStatus.ACTIVE, comment="Авто-бронь из очереди ожидания",
            created_at=int(time.time())
        ))
        entry.notified = 1
        db.flush()  # autoflush выключен: следующая проверка конфликта должна видеть новую бронь
        promoted += 1
    db.commit()
    return promoted
