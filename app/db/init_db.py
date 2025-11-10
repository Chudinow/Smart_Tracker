# app/db/init_db.py
from .connection import engine
from .models import Base

def init_db():
    #Создаёт таблицы в базе данных, если их ещё нет
    Base.metadata.create_all(engine)
    print("База данных инициализирована")

if __name__ == "__main__":
    init_db()
