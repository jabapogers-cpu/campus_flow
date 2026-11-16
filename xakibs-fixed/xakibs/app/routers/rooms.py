"""
CampusFlow - роутер аудиторий
"""
from datetime import date, time, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from ..models import Room, Booking, BookingStatus, User
from ..auth import get_current_user
from ..services.conflicts import check_time_overlap
from ..services.recommend import recommend_rooms
from ..services.pairs import PAIRS

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


class RoomResponse(BaseModel):
    id: int
    name: str
    building: str
    floor: int
    capacity: int
    equipment: List[str]
    
    class Config:
        from_attributes = True


class FreeSlot(BaseModel):
    start: str  # HH:MM
    end: str    # HH:MM


@router.get("", response_model=List[RoomResponse])
def get_rooms(
    building: Optional[str] = Query(None, description="Фильтр по корпусу"),
    min_capacity: Optional[int] = Query(None, alias="minCapacity", description="Минимальная вместимость"),
    equipment: Optional[str] = Query(None, description="Оборудование (через запятую)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Список аудиторий с фильтрами (сценарий 1)
    """
    query = db.query(Room)
    
    if building:
        query = query.filter(Room.building == building)
    
    if min_capacity:
        query = query.filter(Room.capacity >= min_capacity)
    
    if equipment:
        equipment_list = [eq.strip() for eq in equipment.split(",")]
        for eq in equipment_list:
            query = query.filter(Room.equipment.like(f"%{eq}%"))
    
    rooms = query.all()
    
    return [
        RoomResponse(
            id=r.id,
            name=r.name,
            building=r.building,
            floor=r.floor,
            capacity=r.capacity,
            equipment=(r.equipment or "").split(",") if r.equipment else []
        )
        for r in rooms
    ]


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Карточка аудитории
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return RoomResponse(
        id=room.id,
        name=room.name,
        building=room.building,
        floor=room.floor,
        capacity=room.capacity,
        equipment=(room.equipment or "").split(",") if room.equipment else []
    )


@router.get("/{room_id}/free-slots", response_model=List[FreeSlot])
def get_free_slots(
    room_id: int,
    date_param: date = Query(..., alias="date", description="Дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Свободные слоты на указанную дату (сценарий 2)
    Сетка - пары по 1 ч 20 мин (08:00-09:20, 09:30-10:50, ... 20:00-21:20)
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Получаем все активные брони на эту дату
    bookings = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.date == date_param,
        Booking.status == BookingStatus.ACTIVE
    ).all()
    
    # Сетка занятости - пары по 1 ч 20 мин (см. services/pairs.py)
    all_slots = list(PAIRS)
    
    # Фильтруем свободные
    free_slots = []
    for start_t, end_t in all_slots:
        is_free = True
        for booking in bookings:
            if check_time_overlap(start_t, end_t, booking.start_time, booking.end_time):
                is_free = False
                break
        
        if is_free:
            free_slots.append(FreeSlot(
                start=start_t.strftime("%H:%M"),
                end=end_t.strftime("%H:%M")
            ))
    
    return free_slots


@router.get("/recommend/top", response_model=List[dict])
def get_recommended_rooms(
    building: Optional[str] = Query(None),
    min_capacity: Optional[int] = Query(None, alias="minCapacity"),
    equipment: Optional[str] = Query(None),
    date_param: Optional[date] = Query(None, alias="date"),
    start_time_str: Optional[str] = Query(None, alias="startTime", description="HH:MM"),
    end_time_str: Optional[str] = Query(None, alias="endTime", description="HH:MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Рекомендация топ-3 аудиторий (бонусная фича)
    """
    equipment_list = None
    if equipment:
        equipment_list = [eq.strip() for eq in equipment.split(",")]
    
    start_time_obj = None
    end_time_obj = None
    if start_time_str:
        try:
            start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid startTime format, use HH:MM")
    
    if end_time_str:
        try:
            end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid endTime format, use HH:MM")
    
    recommendations = recommend_rooms(
        db=db,
        building=building,
        min_capacity=min_capacity,
        equipment=equipment_list,
        booking_date=date_param,
        start_time=start_time_obj,
        end_time=end_time_obj
    )
    
    return recommendations
