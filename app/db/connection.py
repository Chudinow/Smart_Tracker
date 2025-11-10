from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Локальная sqlite база в корне проекта
DB_URL = "sqlite:///./wlb.db"

# Для sqlite нужно check_same_thread=False при использовании в разных потоках
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

# SessionLocal — фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    """
    Возвращает новую сессию. Вызовите и закройте в finally/with.
    """
    return SessionLocal()
