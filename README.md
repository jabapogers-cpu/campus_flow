##  Быстрый запуск
### Вариант 1: Python 
```bash
# 1. Установите зависимости
pip install -r requirements.txt
# 2. Запустите приложение (создаст БД, seed, запустит сервер)
python run.py
```
### Вариант 2: Docker Compose
```bash
docker compose up
```
**Приложение будет доступно:**
Frontend: http://localhost:8000
API Docs: http://localhost:8000/docs
Живое демо http://localhost:8000/demo 

---

##  Тестовые пользователи
После запуска `python run.py` в базе создаются следующие пользователи:

| Роль        | Логин      | Пароль     |
|-------------|------------|------------|
| Студент 1   | `student1` | `password` |
| Студент 2   | `student2` | `password` |
| Студент 3   | `student3` | `password` |
| Администратор | `admin`  | `admin`    |

На главной странице есть кнопки быстрого входа для удобства.

---

## Архитектура

```
campusflow/
├── app/
│   ├── main.py              # FastAPI приложение
│   ├── models.py            # SQLAlchemy модели (User, Room, Booking, Waitlist)
│   ├── database.py          # Подключение к БД (SQLite)
│   ├── auth.py              # JWT-аутентификация, проверка ролей
│   ├── seed.py              # Seed-данные (10+ аудиторий, пользователи, тестовые брони)
│   ├── services/
│   │   ├── conflicts.py     # Проверка конфликтов броней (ключевая логика)
│   │   ├── conflict_recovery.py  # Альтернативы при конфликте
│   │   ├── recommend.py     # Умные рекомендации аудиторий
│   │   └── stats.py         # Аналитика и статистика
│   ├── routers/
│   │   ├── auth_router.py   # POST /api/auth/login
│   │   ├── rooms.py         # GET /api/rooms, /free-slots, /recommend
│   │   ├── bookings.py      # POST /bookings, /my, DELETE, /waitlist
│   │   └── admin.py         # CRUD rooms, все брони, статистика, CSV-экспорт
│   └── static/
│       ├── index.html       # Главная страница (SPA)
│       ├── demo.html        # Демо-страница с автотестами
│       ├── styles.css       # Тёмная тема, токенизированный дизайн
│       └── app.js           # Frontend логика
├── tests/
│   ├── test_conflicts.py    # Юнит-тесты конфликтов
│   └── test_api.py          # Интеграционные тесты всех 8 сценариев
├── run.py                   # Запуск одной командой
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## API Endpoints

### Аутентификация
- `POST /api/auth/login` — вход, возвращает JWT токен

### Аудитории
- `GET /api/rooms` — список аудиторий с фильтрами (`building`, `minCapacity`, `equipment`)
- `GET /api/rooms/{id}` — карточка аудитории
- `GET /api/rooms/{id}/free-slots?date=YYYY-MM-DD` — свободные слоты на дату
- `GET /api/rooms/recommend/top` — топ-3 рекомендованных аудиторий (бонус)

### Брони
- `POST /api/bookings` — создание брони (409 при конфликте с альтернативами)
- `GET /api/bookings/my` — мои брони
- `DELETE /api/bookings/{id}` — отмена своей брони (403 для чужой)
- `POST /api/bookings/waitlist` — встать в очередь на слот (бонус)
- `GET /api/bookings/waitlist/my` — моя очередь (бонус)

### Админ (требуется роль `admin`)
- `GET /api/admin/bookings` — все брони системы с фильтрами
- `DELETE /api/admin/bookings/{id}` — отмена любой брони
- `POST /api/admin/rooms` — создание аудитории
- `PUT /api/admin/rooms/{id}` — редактирование аудитории
- `DELETE /api/admin/rooms/{id}` — удаление аудитории
- `GET /api/admin/stats/summary` — общая статистика (бонус)
- `GET /api/admin/stats/by-days` — загрузка по дням (бонус)
- `GET /api/admin/stats/by-buildings` — загрузка по корпусам (бонус)
- `GET /api/admin/stats/top-rooms` — топ загруженных аудиторий (бонус)
- `GET /api/admin/export/bookings.csv` — CSV-экспорт броней (бонус)

### Документация
- `GET /docs` — Swagger UI (интерактивная документация API)

---


