# app/db/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Локальная sqlite база в корне проекта
DB_URL = "sqlite:///./wlb.db"

# Для sqlite нужно check_same_thread=False при использовании в разных потоках
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

# SessionLocal — фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Контекстный менеджер для закрытия сессии 
@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
