"""
CampusFlow - роутер администратора
"""
import time
from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import io
import csv
from ..database import get_db
from ..models import Room, Booking, BookingStatus, User
from ..auth import require_admin
from ..services.stats import get_load_by_days, get_load_by_buildings, get_heatmap, get_top_rooms, get_summary_stats

from ..services.waitlist import promote_waitlist

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoomCreateRequest(BaseModel):
    name: str
    building: str
    floor: int
    capacity: int
    equipment: str = ""


class RoomUpdateRequest(BaseModel):
    name: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[int] = None
    capacity: Optional[int] = None
    equipment: Optional[str] = None


class BookingAdminResponse(BaseModel):
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


@router.get("/bookings", response_model=List[BookingAdminResponse])
def get_all_bookings(
    building: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None, alias="dateFrom"),
    date_to: Optional[date] = Query(None, alias="dateTo"),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Все брони системы (сценарий 7)
    """
    query = db.query(Booking)
    
    if building:
        query = query.join(Room).filter(Room.building == building)
    
    if date_from:
        query = query.filter(Booking.date >= date_from)
    
    if date_to:
        query = query.filter(Booking.date <= date_to)
    
    if status_filter:
        try:
            status_enum = BookingStatus(status_filter)
            query = query.filter(Booking.status == status_enum)
        except ValueError:
            pass
    
    bookings = query.order_by(Booking.date.desc(), Booking.start_time.desc()).all()
    
    result = []
    for booking in bookings:
        room = db.query(Room).filter(Room.id == booking.room_id).first()
        user = db.query(User).filter(User.id == booking.user_id).first()
        result.append(BookingAdminResponse(
            id=booking.id,
            room_id=booking.room_id,
            room_name=room.name if room else "Unknown",
            user_id=booking.user_id,
            user_name=user.display_name if user else "Unknown",
            date=booking.date.isoformat(),
            start_time=booking.start_time.strftime("%H:%M"),
            end_time=booking.end_time.strftime("%H:%M"),
            status=booking.status.value,
            comment=booking.comment or "",
            created_at=booking.created_at
        ))
    
    return result


@router.delete("/bookings/{booking_id}", status_code=status.HTTP_200_OK)
def cancel_any_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Отмена любой брони (сценарий 7)
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Booking already cancelled")
    
    booking.status = BookingStatus.CANCELLED
    db.commit()
    
    promoted = promote_waitlist(db, booking.room_id, booking.date)
    
    return {"message": "Booking cancelled", "booking_id": booking_id, "promoted_from_waitlist": promoted}


@router.post("/rooms", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_room(
    request: RoomCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Создание аудитории (сценарий 7)
    """
    room = Room(
        name=request.name,
        building=request.building,
        floor=request.floor,
        capacity=request.capacity,
        equipment=request.equipment
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    
    return {
        "id": room.id,
        "name": room.name,
        "building": room.building,
        "floor": room.floor,
        "capacity": room.capacity,
        "equipment": (room.equipment or "").split(",") if room.equipment else []
    }


@router.put("/rooms/{room_id}", response_model=dict)
def update_room(
    room_id: int,
    request: RoomUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Редактирование аудитории (сценарий 7)
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if request.name is not None:
        room.name = request.name
    if request.building is not None:
        room.building = request.building
    if request.floor is not None:
        room.floor = request.floor
    if request.capacity is not None:
        room.capacity = request.capacity
    if request.equipment is not None:
        room.equipment = request.equipment
    
    db.commit()
    db.refresh(room)
    
    return {
        "id": room.id,
        "name": room.name,
        "building": room.building,
        "floor": room.floor,
        "capacity": room.capacity,
        "equipment": (room.equipment or "").split(",") if room.equipment else []
    }


@router.delete("/rooms/{room_id}", status_code=status.HTTP_200_OK)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Удаление аудитории
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Проверка активных броней
    active_bookings = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.status == BookingStatus.ACTIVE,
        Booking.date >= date.today()
    ).count()
    
    if active_bookings > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete room with {active_bookings} active future bookings"
        )
    
    db.delete(room)
    db.commit()
    
    return {"message": "Room deleted", "room_id": room_id}


@router.get("/stats/summary", response_model=dict)
def get_stats_summary(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Общая статистика (бонусная фича)
    """
    return get_summary_stats(db)


def _stats_period(days: int, ahead: int):
    """Период статистики: N дней назад и M дней вперёд (брони создаются заранее)"""
    days, ahead = max(0, min(days, 30)), max(0, min(ahead, 30))
    return date.today() - timedelta(days=days), date.today() + timedelta(days=ahead)


@router.get("/stats/by-days", response_model=List[dict])
def get_stats_by_days(
    days: int = Query(3, description="Дней назад"),
    ahead: int = Query(7, description="Дней вперёд"),
    building: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Загрузка по дням (бонусная фича)"""
    start_date, end_date = _stats_period(days, ahead)
    return get_load_by_days(db, start_date, end_date, building)


@router.get("/stats/by-buildings", response_model=List[dict])
def get_stats_by_buildings(
    days: int = Query(3),
    ahead: int = Query(7),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Загрузка по корпусам (бонусная фича)"""
    start_date, end_date = _stats_period(days, ahead)
    return get_load_by_buildings(db, start_date, end_date)


@router.get("/stats/heatmap", response_model=dict)
def get_stats_heatmap(
    days: int = Query(3),
    ahead: int = Query(7),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Тепловая карта корпус x день"""
    start_date, end_date = _stats_period(days, ahead)
    return get_heatmap(db, start_date, end_date)


@router.get("/stats/top-rooms", response_model=List[dict])
def get_stats_top_rooms(
    days: int = Query(3),
    ahead: int = Query(7),
    limit: int = Query(10),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Топ загруженных аудиторий (бонусная фича)"""
    start_date, end_date = _stats_period(days, ahead)
    return get_top_rooms(db, start_date, end_date, limit)
