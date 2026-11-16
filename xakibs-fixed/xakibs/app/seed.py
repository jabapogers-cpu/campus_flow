"""
CampusFlow - seed данные
Строго под сценарии приёмки из ТЗ: B-101 имеет id=4, фильтр building=B, minCapacity=20, projector
даёт ровно B-101 и B-204; слот B-101 завтра 14:00-15:00 свободен.
"""
import time
from datetime import date, time as dtime, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal, init_db
from .models import User, Room, Booking, BookingStatus, UserRole
from .auth import get_password_hash

USERS = [  # login, пароль, роль, имя
    ("student1", "password", UserRole.STUDENT, "Иван Петров"),
    ("student2", "password", UserRole.STUDENT, "Мария Иванова"),
    ("student3", "password", UserRole.STUDENT, "Алексей Сидоров"),
    ("admin", "admin", UserRole.ADMIN, "Администратор"),
]

ROOMS = [  # порядок задаёт id: B-101 -> 4
    ("A-101", "A", 1, 15, "whiteboard"),
    ("A-205", "A", 2, 25, "projector,whiteboard"),
    ("A-310", "A", 3, 30, "projector,computers"),
    ("B-101", "B", 1, 30, "projector,whiteboard"),
    ("B-204", "B", 2, 24, "projector,computers"),
    ("B-305", "B", 3, 20, "whiteboard"),
    ("B-408", "B", 4, 50, "whiteboard,computers,smartboard"),  # без проектора: не попадает в фильтр сценария 1
    ("A-412", "A", 4, 40, "projector,whiteboard,computers"),
    ("C-102", "C", 1, 18, "projector"),
    ("C-201", "C", 2, 35, "projector,whiteboard,computers"),
    ("C-315", "C", 3, 28, "projector,whiteboard"),
    ("C-420", "C", 4, 45, "projector,computers,smartboard"),
]

BOOKINGS = [  # аудитория, логин, смещение в днях, начало, конец (по сетке пар), комментарий
    ("C-420", "student1", -1, (9, 30), (10, 50), "Вчерашний семинар"),
    ("A-101", "student1", 0, (11, 0), (12, 20), "Лекция по математике"),
    ("A-205", "student2", 0, (14, 0), (15, 20), "Семинар"),
    ("B-204", "student1", 1, (9, 30), (10, 50), "Подготовка к экзамену"),  # завтра; B-101 14:00 свободна
    ("B-204", "student2", 1, (17, 0), (18, 20), "Групповой проект"),
    ("B-305", "student3", 1, (8, 0), (9, 20), "Консультация"),
    ("A-310", "student3", 2, (9, 30), (10, 50), "Курсовая работа"),
    ("B-101", "student2", 2, (14, 0), (15, 20), "Репетиция доклада"),
    ("C-201", "student1", 2, (12, 30), (13, 50), "Практикум"),
    ("B-408", "student2", 3, (11, 0), (12, 20), "Собрание потока"),
    ("C-102", "student3", 3, (15, 30), (16, 50), "Кружок"),
]


def seed_database(db: Session) -> bool:
    """Заполняет пустую БД. Если пользователи уже есть — ничего не делает (возвращает False)."""
    if db.query(User).count() > 0:
        return False

    users = {}
    for login, password, role, name in USERS:
        u = User(login=login, password_hash=get_password_hash(password), role=role, display_name=name)
        db.add(u)
        users[login] = u
    rooms = {}
    for name, building, floor, capacity, equipment in ROOMS:  # добавляем по одной: id идут по порядку списка
        r = Room(name=name, building=building, floor=floor, capacity=capacity, equipment=equipment)
        db.add(r)
        db.flush()
        rooms[name] = r
    db.flush()

    today, now_ts = date.today(), int(time.time())
    for i, (room, login, offset, start, end, comment) in enumerate(BOOKINGS):
        db.add(Booking(
            room_id=rooms[room].id, user_id=users[login].id, date=today + timedelta(days=offset),
            start_time=dtime(*start), end_time=dtime(*end), status=BookingStatus.ACTIVE,
            comment=comment, created_at=now_ts - 600 * (len(BOOKINGS) - i)
        ))
    db.commit()
    return True


def init_database():
    """Создание таблиц и загрузка seed-данных (идемпотентно)"""
    init_db()
    db = SessionLocal()
    try:
        if seed_database(db):
            print(f"✅ Создано: {len(USERS)} пользователя, {len(ROOMS)} аудиторий, {len(BOOKINGS)} броней")
        else:
            print("⚠️  База данных уже содержит данные, seed пропущен (удалите campusflow.db для чистого старта)")
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
