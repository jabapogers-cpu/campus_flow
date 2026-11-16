"""
CampusFlow - интеграционные тесты: сценарии приёмки 1-8 из ТЗ + граничные случаи.
Запуск: pytest tests/ -v
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.seed import seed_database

client = TestClient(app)
TOMORROW = str(date.today() + timedelta(days=1))


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Чистая база + seed (это и есть «запуск с нуля»)"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def auth(login, password="password"):
    r = client.post("/api/auth/login", json={"login": login, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def book(headers, room_id, start, end, day=TOMORROW, comment=""):
    return client.post("/api/bookings", headers=headers, json={
        "room_id": room_id, "date": day, "start_time": start, "end_time": end, "comment": comment})


def room_id(headers, name):
    return next(r["id"] for r in client.get("/api/rooms", headers=headers).json() if r["name"] == name)


def test_scenario_1_filters():
    h = auth("student1")
    r = client.get("/api/rooms?building=B&minCapacity=20&equipment=projector", headers=h)
    assert r.status_code == 200
    assert sorted(x["name"] for x in r.json()) == ["B-101", "B-204"]
    # корпус A, 15 человек: только подходящие
    rooms = client.get("/api/rooms?building=A&minCapacity=15", headers=h).json()
    assert rooms and all(x["building"] == "A" and x["capacity"] >= 15 for x in rooms)


def test_scenario_2_free_slots():
    h = auth("student1")
    rid = room_id(h, "B-101")
    assert rid == 4  # как в приложении к ТЗ
    r = client.get(f"/api/rooms/{rid}/free-slots?date={TOMORROW}", headers=h)
    assert r.status_code == 200
    slots = r.json()
    assert {"start": "14:00", "end": "15:20"} in slots  # пара 14:00-15:20 свободна, значит свободен и 14:00-15:00
    assert all(s["end"] > s["start"] for s in slots)


def test_scenario_3_create_booking():
    h = auth("student1")
    r = book(h, 4, "14:00", "15:00")
    assert r.status_code == 201
    mine = client.get("/api/bookings/my", headers=h).json()
    assert r.json()["id"] in [b["id"] for b in mine]


def test_scenario_4_conflict_409():
    h2 = auth("student2")
    r = book(h2, 4, "14:00", "15:00")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "BOOKING_CONFLICT" and detail["message"]
    assert "nearby_slots" in detail["alternatives"] and "similar_rooms" in detail["alternatives"]


def test_scenario_6_foreign_cancel_403():
    h1, h2 = auth("student1"), auth("student2")
    bid = next(b["id"] for b in client.get("/api/bookings/my", headers=h1).json()
               if b["room_id"] == 4 and b["date"] == TOMORROW and b["status"] == "active")
    assert client.delete(f"/api/bookings/{bid}", headers=h2).status_code == 403
    still = next(b for b in client.get("/api/bookings/my", headers=h1).json() if b["id"] == bid)
    assert still["status"] == "active"


def test_scenario_5_cancel_own_returns_slot():
    h1 = auth("student1")
    bid = next(b["id"] for b in client.get("/api/bookings/my", headers=h1).json()
               if b["room_id"] == 4 and b["date"] == TOMORROW and b["status"] == "active")
    assert client.delete(f"/api/bookings/{bid}", headers=h1).status_code == 200
    starts = {s["start"] for s in client.get(f"/api/rooms/4/free-slots?date={TOMORROW}", headers=h1).json()}
    assert "14:00" in starts
    mine = client.get("/api/bookings/my", headers=h1).json()
    assert next(b for b in mine if b["id"] == bid)["status"] == "cancelled"


def test_scenario_7_admin_sees_all_and_cancels_any():
    ha, h2 = auth("admin", "admin"), auth("student2")
    created = book(h2, room_id(ha, "C-315"), "10:00", "11:00").json()
    allb = client.get("/api/admin/bookings", headers=ha)
    assert allb.status_code == 200 and created["id"] in [b["id"] for b in allb.json()]
    assert client.delete(f"/api/admin/bookings/{created['id']}", headers=ha).status_code == 200
    mine = client.get("/api/bookings/my", headers=h2).json()
    assert next(b for b in mine if b["id"] == created["id"])["status"] == "cancelled"
    # права: студент не видит админ-методов, админ не создаёт брони
    assert client.get("/api/admin/bookings", headers=h2).status_code == 403
    assert client.get("/api/admin/stats/summary", headers=h2).status_code == 403
    assert book(ha, 4, "09:00", "10:00").status_code == 403


def test_scenario_8_cold_start_docs_and_seed():
    assert client.get("/docs").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"
    h = auth("student1")
    assert len(client.get("/api/rooms", headers=h).json()) >= 10
    for login, pw in (("student1", "password"), ("student2", "password"), ("student3", "password"), ("admin", "admin")):
        auth(login, pw)


def test_touching_boundaries_and_overlaps():
    h1, h2 = auth("student1"), auth("student2")
    day = str(date.today() + timedelta(days=9))
    rid = room_id(h1, "A-101")
    assert book(h1, rid, "12:00", "13:00", day).status_code == 201
    assert book(h2, rid, "13:00", "14:00", day).status_code == 201  # касание справа
    assert book(h2, rid, "11:00", "12:00", day).status_code == 201  # касание слева
    for s, e in (("12:30", "13:30"), ("11:30", "12:30"), ("12:15", "12:45"), ("10:00", "15:00")):
        assert book(h2, rid, s, e, day).status_code == 409, (s, e)


def test_validation_and_auth():
    h = auth("student1")
    assert book(h, 4, "15:00", "14:00").status_code == 400
    assert book(h, 4, "07:00", "09:00").status_code == 400
    assert book(h, 999, "10:00", "11:00").status_code == 404
    assert client.get("/api/rooms").status_code == 401


def test_waitlist_auto_promotion():
    h1, h2 = auth("student1"), auth("student2")
    day = str(date.today() + timedelta(days=12))
    rid = room_id(h1, "A-310")
    bid = book(h1, rid, "10:00", "11:00", day).json()["id"]
    w = client.post("/api/bookings/waitlist", headers=h2,
                    json={"room_id": rid, "date": day, "start_time": "10:00", "end_time": "11:00"})
    assert w.status_code == 201
    assert client.delete(f"/api/bookings/{bid}", headers=h1).json()["promoted_from_waitlist"] == 1
    mine = client.get("/api/bookings/my", headers=h2).json()
    assert any(b["date"] == day and b["room_id"] == rid and b["status"] == "active" for b in mine)


def test_admin_room_crud():
    ha = auth("admin", "admin")
    r = client.post("/api/admin/rooms", headers=ha, json={
        "name": "Test-301", "building": "C", "floor": 3, "capacity": 40, "equipment": "whiteboard"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.delete(f"/api/admin/rooms/{rid}", headers=ha).status_code == 200


def test_recommendations_have_names_and_reasons():
    h = auth("student1")
    r = client.get(f"/api/rooms/recommend/top?building=B&minCapacity=20&equipment=projector&date={TOMORROW}"
                   "&startTime=14:00&endTime=15:00", headers=h)
    assert r.status_code == 200
    recs = r.json()
    assert 1 <= len(recs) <= 3
    for rec in recs:
        assert rec["id"] and rec["name"] and rec["room_name"] == rec["name"]
        assert rec["building"] == "B" and "projector" in rec["equipment"]
        assert rec["reasons"] and rec["available"] is True


def test_free_slots_are_pairs_of_80_minutes():
    h = auth("student1")
    slots = client.get(f"/api/rooms/4/free-slots?date={TOMORROW}", headers=h).json()
    for s in slots:
        sh, sm = map(int, s["start"].split(":"))
        eh, em = map(int, s["end"].split(":"))
        assert (eh * 60 + em) - (sh * 60 + sm) == 80


def test_admin_stats_endpoints():
    ha, hs = auth("admin", "admin"), auth("student1")
    for path in ("summary", "by-buildings", "by-days", "top-rooms", "heatmap"):
        assert client.get(f"/api/admin/stats/{path}", headers=ha).status_code == 200, path
        assert client.get(f"/api/admin/stats/{path}", headers=hs).status_code == 403, path
    blds = client.get("/api/admin/stats/by-buildings", headers=ha).json()
    assert {b["building"] for b in blds} >= {"A", "B", "C"} and any(b["bookings_count"] for b in blds)
    heat = client.get("/api/admin/stats/heatmap", headers=ha).json()
    assert len(heat["cells"]) == len(heat["days"]) * len(heat["buildings"])
    assert all(0 <= c["load_percent"] <= 100 for c in heat["cells"])
    days = client.get("/api/admin/stats/by-days", headers=ha).json()
    assert all(0 <= d["load_percent"] <= 100 for d in days)
