# app/db/init_db.py
from sqlalchemy import text
from .connection import engine
from .models import Base

def _ensure_columns_sqlite():
    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(habits)")).fetchall()
        existing = {c[1] for c in cols}

        if "kind" not in existing:
            conn.execute(text("ALTER TABLE habits ADD COLUMN kind VARCHAR NOT NULL DEFAULT 'counter'"))

        if "target" not in existing:
            conn.execute(text("ALTER TABLE habits ADD COLUMN target INTEGER"))

        # ✅ ДОБАВИТЬ
        if "is_active" not in existing:
            conn.execute(text("ALTER TABLE habits ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))

def init_db():
    Base.metadata.create_all(engine)
    _ensure_columns_sqlite()
    print("База данных инициализирована")
