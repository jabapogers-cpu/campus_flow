"""
CampusFlow - скрипт запуска одной командой
Создаёт БД, загружает seed-данные, запускает сервер
"""
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, SessionLocal
from app.seed import init_database

def setup_database():
    """Инициализация базы данных перед запуском"""
    print("🚀 CampusFlow - инициализация базы данных...\n")
    
    # Создание таблиц
    print("📦 Создание таблиц...")
    Base.metadata.create_all(bind=engine)
    
    # Загрузка seed-данных
    print("🌱 Загрузка тестовых данных...")
    try:
        init_database()
        print("✅ Тестовые данные загружены\n")
    except Exception as e:
        print(f"⚠️  Ошибка загрузки данных: {e}\n")


if __name__ == "__main__":
    # Инициализация БД
    setup_database()
    
    # Печатаем информацию
    print("="*60)
    print("✅ CampusFlow готов к работе!")
    print("="*60)
    print("\n📚 Доступные пользователи для входа:")
    print("   Студент 1: login=student1, password=password")
    print("   Студент 2: login=student2, password=password")
    print("   Админ:     login=admin, password=admin")
    print("\n🌐 Приложение доступно по адресам:")
    print("   Frontend: http://localhost:8000")
    print("   API Docs: http://localhost:8000/docs")
    print("   Demo:     http://localhost:8000/demo")
    print("\n🛑 Для остановки: Ctrl+C")
    print("="*60 + "\n")
    
    # Запуск сервера
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
