"""
CampusFlow - аналитика и статистика (бонусная фича)
Считается на Python: не зависит от диалекта SQL. Загрузка = занятые минуты / (аудитории * 14 ч * дни)
"""
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import Room, User, Booking, BookingStatus

DAY_MINUTES = 14 * 60  # окно бронирования 08:00-22:00


def _minutes(booking: Booking) -> int:
    return (booking.end_time.hour * 60 + booking.end_time.minute) - (booking.start_time.hour * 60 + booking.start_time.minute)


def _days(start_date: date, end_date: date) -> List[date]:
    return [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]


def _active(db: Session, start_date: date, end_date: date):
    return db.query(Booking, Room).join(Room, Room.id == Booking.room_id).filter(
        Booking.date >= start_date, Booking.date <= end_date, Booking.status == BookingStatus.ACTIVE
    ).all()


def _pct(minutes: float, rooms: int, days: int) -> float:
    available = rooms * days * DAY_MINUTES
    return round(min(100.0, minutes / available * 100), 1) if available else 0.0


def get_load_by_days(db: Session, start_date: date, end_date: date, building: Optional[str] = None) -> List[Dict[str, Any]]:
    rooms_q = db.query(Room)
    if building:
        rooms_q = rooms_q.filter(Room.building == building)
    rooms_n = rooms_q.count()
    minutes, counts = {}, {}
    for booking, room in _active(db, start_date, end_date):
        if building and room.building != building:
            continue
        minutes[booking.date] = minutes.get(booking.date, 0) + _minutes(booking)
        counts[booking.date] = counts.get(booking.date, 0) + 1
    return [{
        "date": d.isoformat(),
        "bookings_count": counts.get(d, 0),
        "hours": round(minutes.get(d, 0) / 60, 1),
        "load_percent": _pct(minutes.get(d, 0), rooms_n, 1)
    } for d in _days(start_date, end_date)]


def get_load_by_buildings(db: Session, start_date: date, end_date: date) -> List[Dict[str, Any]]:
    rooms_per_building = {}
    for room in db.query(Room).all():
        rooms_per_building[room.building] = rooms_per_building.get(room.building, 0) + 1
    minutes, counts = {}, {}
    for booking, room in _active(db, start_date, end_date):
        minutes[room.building] = minutes.get(room.building, 0) + _minutes(booking)
        counts[room.building] = counts.get(room.building, 0) + 1
    n_days = (end_date - start_date).days + 1
    return [{
        "building": b,
        "rooms_count": rooms_per_building[b],
        "bookings_count": counts.get(b, 0),
        "hours": round(minutes.get(b, 0) / 60, 1),
        "load_percent": _pct(minutes.get(b, 0), rooms_per_building[b], n_days)
    } for b in sorted(rooms_per_building)]


def get_heatmap(db: Session, start_date: date, end_date: date) -> Dict[str, Any]:
    """Тепловая карта корпус x день"""
    rooms_per_building = {}
    for room in db.query(Room).all():
        rooms_per_building[room.building] = rooms_per_building.get(room.building, 0) + 1
    minutes = {}
    for booking, room in _active(db, start_date, end_date):
        key = (room.building, booking.date)
        minutes[key] = minutes.get(key, 0) + _minutes(booking)
    days = _days(start_date, end_date)
    buildings = sorted(rooms_per_building)
    return {
        "days": [d.isoformat() for d in days],
        "buildings": buildings,
        "cells": [{
            "building": b, "date": d.isoformat(),
            "load_percent": _pct(minutes.get((b, d), 0), rooms_per_building[b], 1)
        } for b in buildings for d in days]
    }


def get_top_rooms(db: Session, start_date: date, end_date: date, limit: int = 10) -> List[Dict[str, Any]]:
    stats = {}
    for booking, room in _active(db, start_date, end_date):
        item = stats.setdefault(room.id, {"room_id": room.id, "room_name": room.name, "building": room.building,
                                          "bookings_count": 0, "minutes": 0})
        item["bookings_count"] += 1
        item["minutes"] += _minutes(booking)
    ranked = sorted(stats.values(), key=lambda x: (-x["bookings_count"], -x["minutes"]))[:limit]
    return [{"room_id": r["room_id"], "room_name": r["room_name"], "building": r["building"],
             "bookings_count": r["bookings_count"], "hours": round(r["minutes"] / 60, 1)} for r in ranked]


def get_summary_stats(db: Session) -> Dict[str, Any]:
    today = date.today()
    return {
        "total_rooms": db.query(Room).count(),
        "total_users": db.query(User).count(),
        "active_bookings": db.query(Booking).filter(Booking.status == BookingStatus.ACTIVE, Booking.date >= today).count(),
        "week_bookings": db.query(Booking).filter(
            Booking.status == BookingStatus.ACTIVE, Booking.date >= today, Booking.date <= today + timedelta(days=6)
        ).count()
    }
