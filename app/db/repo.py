# app/db/repo.py
from typing import Optional, List
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from .connection import get_session
from .models import User, Habit, HabitLog, MoodEntry

# ----- UTILS ---------

# Получаем пользователя по id
def get_user_by_id(user_id: int) -> Optional[User]:
    with get_session() as db:
        return db.query(User).get(user_id)

# Получаем привычку по id 
def get_habit_by_id(habit_id: int) -> Optional[Habit]:
    with get_session() as db:
        return db.query(Habit).get(habit_id)

# Получаем лист привычек по id пользователя
def get_user_habits(user_id: int) -> list[Habit]:
    with get_session() as db:
        return db.query(Habit).filter(Habit.user_id == user_id).all()
    
# Поиск пользователя в БД через username
def get_user_by_username(username: str) -> Optional[User]:
    with get_session() as db:
        return db.query(User).filter(User.username == username).first()

# ----- USER REPO ---------

# Создание пользователя, на выходе тип User с обновленными данными
def create_user(username: str, password_hash: str, display_name: Optional[str] = None) -> User:
    with get_session() as db:
        user = User(username=username, password_hash=password_hash, display_name=display_name)
        db.add(user)
        db.commit()
        db.refresh(user)    # обновляем объект (получаем id)
        return user


# ----- HABIT REPO --------

# Создание привычки
def create_habit(user_id: int, name: str, description: str = None, frequency: str = None) -> Habit:
    with get_session() as db:
        habit = Habit(user_id=user_id, name=name, description=description, frequency=frequency)
        db.add(habit)
        db.commit()
        db.refresh(habit)
        return habit

# ----- HABITLOG REPO -----

# Создаем лог привычки 
def add_habit_log_safe(habit_id: int, day: date, completed: bool,
                       value: Optional[int] = None, note: Optional[str] = None) -> HabitLog:
    """
    Безопасная запись/обновление лога:
    - Берёт owner_id из Habit (источник правды).
    - Если лог за день уже есть — обновляет его.
    - Обрабатывает редкую гонку при одновременной вставке.
    """
    with get_session() as db:
        habit = db.query(Habit).get(habit_id)
        if not habit:
            raise ValueError("Habit not found")

        owner_id = habit.user_id

        # попробуем найти существующую запись
        entry = db.query(HabitLog).filter_by(habit_id=habit_id, date=day).first()
        if entry:
            entry.completed = completed
            if value is not None:
                entry.value = value
            if note is not None:
                entry.note = note
            db.commit()
            db.refresh(entry)
            return entry

        # создаём новую запись (указываем user_id из habit)
        new = HabitLog(
            user_id=owner_id,
            habit_id=habit_id,
            date=day,
            completed=completed,
            value=value,
            note=note,
            created_at=datetime.utcnow()
        )
        db.add(new)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # редкая гонка — другой процесс вставил одновременно, апдейтим существующую
            existing = db.query(HabitLog).filter_by(habit_id=habit_id, date=day).first()
            if not existing:
                raise
            existing.completed = completed
            if value is not None:
                existing.value = value
            if note is not None:
                existing.note = note
            db.commit()
            db.refresh(existing)
            return existing

        db.refresh(new)
        return new
