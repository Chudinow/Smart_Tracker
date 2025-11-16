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

# ЧТЕНИЕ ЛОГОВ ПРИВЫЧЕК

def get_logs_for_habit(habit_id: int,
                       start: Optional[date] = None,
                       end: Optional[date] = None) -> list[HabitLog]:
    """Вернуть все логи одной привычки за период [start; end]."""
    with get_session() as db:
        q = db.query(HabitLog).filter(HabitLog.habit_id == habit_id)
        if start is not None:
            q = q.filter(HabitLog.date >= start)
        if end is not None:
            q = q.filter(HabitLog.date <= end)
        return q.order_by(HabitLog.date).all()


def get_logs_for_user(user_id: int,
                      start: Optional[date] = None,
                      end: Optional[date] = None) -> list[HabitLog]:
    """Вернуть все логи пользователя за период [start; end]."""
    with get_session() as db:
        q = db.query(HabitLog).filter(HabitLog.user_id == user_id)
        if start is not None:
            q = q.filter(HabitLog.date >= start)
        if end is not None:
            q = q.filter(HabitLog.date <= end)
        return q.order_by(HabitLog.date).all()


# ------------------------
# MOOD ENTRY REPO
# ------------------------

def create_mood_entry(user_id: int,
                      day: date,
                      mood_score: Optional[int] = None,
                      text_note: Optional[str] = None) -> MoodEntry:
    """Создать запись настроения пользователя за день."""
    with get_session() as db:
        entry = MoodEntry(
            user_id=user_id,
            date=day,
            mood_score=mood_score,
            text_note=text_note,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

# ФУНКЦИИ ДЛЯ ML

def get_mood_entries(user_id: int,
                     start: Optional[date] = None,
                     end: Optional[date] = None) -> list[MoodEntry]:
    """Получить записи настроения пользователя за период."""
    with get_session() as db:
        q = db.query(MoodEntry).filter(MoodEntry.user_id == user_id)
        if start is not None:
            q = q.filter(MoodEntry.date >= start)
        if end is not None:
            q = q.filter(MoodEntry.date <= end)
        return q.order_by(MoodEntry.date).all()


def update_mood_sentiment(entry_id: int,
                          label: str,
                          confidence: float) -> MoodEntry:
    """Обновить результат анализа настроения."""
    with get_session() as db:
        entry = db.query(MoodEntry).get(entry_id)
        if not entry:
            raise ValueError("MoodEntry not found")
        entry.sentiment_label = label
        entry.sentiment_confidence = confidence
        db.commit()
        db.refresh(entry)
        return entry

