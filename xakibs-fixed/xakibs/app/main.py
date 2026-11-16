"""
CampusFlow - главный файл приложения
FastAPI backend + статические файлы frontend
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from .routers import auth_router, rooms, bookings, admin

# Создание приложения
app = FastAPI(
    title="CampusFlow API",
    description="Умное бронирование аудиторий университета",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS для frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth_router.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(admin.router)

# Статические файлы
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    @app.get("/")
    def serve_index():
        return FileResponse(str(static_path / "index.html"))
    
    @app.get("/demo")
    def serve_demo():
        demo_file = static_path / "demo.html"
        if demo_file.exists():
            return FileResponse(str(demo_file))
        return {"message": "Demo page not found"}


@app.get("/api/health")
def health_check():
    """Проверка работоспособности API"""
    return {"status": "ok", "service": "CampusFlow"}
