"""
CampusFlow - модели данных
User, Room, Booking
"""
from datetime import datetime, date, time
from typing import Optional
from sqlalchemy import Column, Integer, String, Date, Time, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class BookingStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    display_name = Column(String(100), nullable=False)
    
    bookings = relationship("Booking", back_populates="user")


class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    building = Column(String(10), nullable=False, index=True)
    floor = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False)
    equipment = Column(Text, nullable=True)  # JSON-like: "projector,whiteboard,computers"
    
    bookings = relationship("Booking", back_populates="room")


class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(SQLEnum(BookingStatus), nullable=False, default=BookingStatus.ACTIVE, index=True)
    comment = Column(Text, nullable=True)
    created_at = Column(Integer, nullable=False)  # Unix timestamp
    
    room = relationship("Room", back_populates="bookings")
    user = relationship("User", back_populates="bookings")
    waitlist = relationship("WaitlistEntry", back_populates="booking", cascade="all, delete-orphan")


class WaitlistEntry(Base):
    __tablename__ = "waitlist"
    
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(Integer, nullable=False)
    notified = Column(Integer, nullable=False, default=0)  # 0=pending, 1=notified
    
    booking = relationship("Booking", back_populates="waitlist")
    user = relationship("User")
    room = relationship("Room")
