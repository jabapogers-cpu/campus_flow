"""
CampusFlow - роутер бронирований
"""
import time as time_module
from datetime import date, time, datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from ..database import get_db
from ..models import Booking, BookingStatus, User, UserRole, Room, WaitlistEntry
from ..auth import get_current_user
from ..services.conflicts import find_booking_conflicts, validate_booking_time
from ..services.conflict_recovery import generate_conflict_alternatives
from ..services.waitlist import promote_waitlist

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class BookingCreateRequest(BaseModel):
    room_id: int
    date: date
    start_time: str  # HH:MM
    end_time: str    # HH:MM
    comment: str = ""
    
    @field_validator('start_time', 'end_time')
    def validate_time_format(cls, v):
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format")


class BookingResponse(BaseModel):
    id: int
    room_id: int
    room_name: str
    user_id: int
    user_name: str
    date: str
    start_time: str
    end_time: str
    status: str
    comment: str
    created_at: int
    
    class Config:
        from_attributes = True


class WaitlistCreateRequest(BaseModel):
    room_id: int
    date: date
    start_time: str
    end_time: str


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    request: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создание брони (сценарии 3, 4)
    При конфликте возвращает 409 с альтернативами
    """
    # По матрице прав ТЗ администратор броней не создаёт
    if current_user.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    
    # Проверка существования аудитории
    room = db.query(Room).filter(Room.id == request.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Парсинг времени
    try:
        start_time_obj = datetime.strptime(request.start_time, "%H:%M").time()
        end_time_obj = datetime.strptime(request.end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format, use HH:MM")
    
    # Валидация временного интервала
    is_valid, error_msg = validate_booking_time(start_time_obj, end_time_obj)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Проверка конфликтов
    conflicts = find_booking_conflicts(
        db=db,
        room_id=request.room_id,
        booking_date=request.date,
        start_time=start_time_obj,
        end_time=end_time_obj
    )
    
    if conflicts:
        # Генерируем альтернативы
        alternatives = generate_conflict_alternatives(
            db=db,
            room_id=request.room_id,
            booking_date=request.date,
            start_time=start_time_obj,
            end_time=end_time_obj
        )
        
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "BOOKING_CONFLICT",
                "message": f"Аудитория {room.name} занята на {request.start_time}–{request.end_time}",
                "alternatives": alternatives
            }
        )
    
    # Создание брони
    booking = Booking(
        room_id=request.room_id,
        user_id=current_user.id,
        date=request.date,
        start_time=start_time_obj,
        end_time=end_time_obj,
        status=BookingStatus.ACTIVE,
        comment=request.comment,
        created_at=int(time_module.time())
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return BookingResponse(
        id=booking.id,
        room_id=booking.room_id,
        room_name=room.name,
        user_id=booking.user_id,
        user_name=current_user.display_name,
        date=booking.date.isoformat(),
        start_time=booking.start_time.strftime("%H:%M"),
        end_time=booking.end_time.strftime("%H:%M"),
        status=booking.status.value,
        comment=booking.comment or "",
        created_at=booking.created_at
    )


@router.get("/my", response_model=List[BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Мои брони (сценарий 3)
    """
    bookings = db.query(Booking).filter(
        Booking.user_id == current_user.id
    ).order_by(Booking.date.desc(), Booking.start_time.desc()).all()
    
    result = []
    for booking in bookings:
        room = db.query(Room).filter(Room.id == booking.room_id).first()
        result.append(BookingResponse(
            id=booking.id,
            room_id=booking.room_id,
            room_name=room.name if room else "Unknown",
            user_id=booking.user_id,
            user_name=current_user.display_name,
            date=booking.date.isoformat(),
            start_time=booking.start_time.strftime("%H:%M"),
            end_time=booking.end_time.strftime("%H:%M"),
            status=booking.status.value,
            comment=booking.comment or "",
            created_at=booking.created_at
        ))
    
    return result


@router.delete("/{booking_id}", status_code=status.HTTP_200_OK)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Отмена своей брони (сценарии 5, 6)
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Проверка прав: только владелец может отменить свою бронь
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FORBIDDEN"
        )
    
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Booking already cancelled")
    
    booking.status = BookingStatus.CANCELLED
    db.commit()
    
    # Слот освободился: первый в очереди получает бронь автоматически
    promoted = promote_waitlist(db, booking.room_id, booking.date)
    
    return {"message": "Booking cancelled", "booking_id": booking_id, "promoted_from_waitlist": promoted}


@router.post("/waitlist", status_code=status.HTTP_201_CREATED)
def join_waitlist(
    request: WaitlistCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Встать в очередь на слот (бонусная фича)
    """
    # Проверка существования аудитории
    room = db.query(Room).filter(Room.id == request.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Парсинг времени
    try:
        start_time_obj = datetime.strptime(request.start_time, "%H:%M").time()
        end_time_obj = datetime.strptime(request.end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format")
    
    # Находим конфликтующую бронь
    conflicts = find_booking_conflicts(
        db=db,
        room_id=request.room_id,
        booking_date=request.date,
        start_time=start_time_obj,
        end_time=end_time_obj
    )
    
    if not conflicts:
        raise HTTPException(status_code=400, detail="Slot is free, book directly")
    
    if any(c.user_id == current_user.id for c in conflicts):
        raise HTTPException(status_code=400, detail="Это ваша собственная бронь")
    
    already = db.query(WaitlistEntry).filter(
        WaitlistEntry.user_id == current_user.id,
        WaitlistEntry.room_id == request.room_id,
        WaitlistEntry.date == request.date,
        WaitlistEntry.start_time == start_time_obj,
        WaitlistEntry.notified == 0
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="Вы уже стоите в очереди на эту пару")
    
    # Создаём запись в очереди
    waitlist_entry = WaitlistEntry(
        booking_id=conflicts[0].id,
        user_id=current_user.id,
        room_id=request.room_id,
        date=request.date,
        start_time=start_time_obj,
        end_time=end_time_obj,
        created_at=int(time_module.time()),
        notified=0
    )
    db.add(waitlist_entry)
    db.commit()
    
    position = db.query(WaitlistEntry).filter(
        WaitlistEntry.room_id == request.room_id,
        WaitlistEntry.date == request.date,
        WaitlistEntry.start_time == start_time_obj,
        WaitlistEntry.notified == 0
    ).count()
    return {"message": "Added to waitlist", "position": position}


@router.get("/waitlist/my", response_model=List[dict])
def get_my_waitlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Моя очередь
    """
    entries = db.query(WaitlistEntry).filter(
        WaitlistEntry.user_id == current_user.id
    ).order_by(WaitlistEntry.created_at).all()
    
    result = []
    for entry in entries:
        room = db.query(Room).filter(Room.id == entry.room_id).first()
        result.append({
            "id": entry.id,
            "room_name": room.name if room else "Unknown",
            "date": entry.date.isoformat(),
            "start_time": entry.start_time.strftime("%H:%M"),
            "end_time": entry.end_time.strftime("%H:%M"),
            "notified": bool(entry.notified),
            "created_at": entry.created_at
        })
    
    return result
