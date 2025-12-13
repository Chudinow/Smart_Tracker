# app/db/repo.py
from typing import Optional, List
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from .connection import get_session
from .models import User, Habit, HabitLog, MoodEntry
from collections import defaultdict

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

# Получить всех пользователей
def get_all_users() -> list[User]:
    with get_session() as db:
        return db.query(User).all()

# Получить все привычки
def get_all_habits() -> list[Habit]:
    with get_session() as db:
        return db.query(Habit).all()

def get_daily_state_for_user(user_id: int, day: date):
    """Вернуть привычки пользователя + их лог на конкретный день."""
    with get_session() as db:
        habits = (
            db.query(Habit)
            .filter(Habit.user_id == user_id, Habit.is_active == True)
            .all()
        )

        logs = (
            db.query(HabitLog)
            .filter(
                HabitLog.user_id == user_id,
                HabitLog.date == day,
            )
            .all()
        )
        logs_by_habit = {log.habit_id: log for log in logs}

        result = []
        for h in habits:
            result.append(
                {
                    "habit_id": h.id,
                    "habit_name": h.name,
                    "description": h.description,
                    "frequency": h.frequency,
                    "kind": h.kind,
                    "target": h.target,
                    "completed": logs_by_habit.get(h.id).completed if h.id in logs_by_habit else False,
                    "value": (logs_by_habit.get(h.id).value if h.id in logs_by_habit else 0) or 0,
                }
            )
        return result

def get_mood_stats(user_id: int, start: date, end: date):
    entries = get_mood_entries(user_id, start, end)
    if not entries:
        return {"entries": [], "avg_score": None}

    scores = [e.mood_score for e in entries if e.mood_score is not None]
    avg_score = sum(scores) / len(scores) if scores else None

    return {
        "entries": entries,
        "avg_score": avg_score,
    }


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
def create_habit(user_id: int, name: str, description: str = None, frequency: str = None, kind: str = "counter", target: Optional[int] = None) -> Habit:
    with get_session() as db:
        habit = Habit(
            user_id=user_id,
            name=name,
            description=description,
            frequency=frequency,
            kind=kind,
            target=target,
        )
        db.add(habit)
        db.commit()
        db.refresh(habit)
        return habit

def archive_habit_for_user(user_id: int, habit_id: int) -> bool:
    with get_session() as db:
        habit = (
            db.query(Habit)
            .filter(Habit.id == habit_id, Habit.user_id == user_id)
            .first()
        )
        if not habit:
            return False
        habit.is_active = False
        db.commit()
        return True
    
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

def update_habit(
    habit_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    frequency: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Habit:
    with get_session() as db:
        habit = db.query(Habit).get(habit_id)
        if not habit:
            raise ValueError("Habit not found")

        if name is not None:
            habit.name = name
        if description is not None:
            habit.description = description
        if frequency is not None:
            habit.frequency = frequency
        if is_active is not None:
            habit.is_active = is_active

        db.commit()
        db.refresh(habit)
        return habit

def delete_habit(habit_id: int) -> None:
    with get_session() as db:
        habit = db.query(Habit).get(habit_id)
        if not habit:
            return
        db.delete(habit)
        db.commit()


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

# app/db/repo.py

def upsert_mood_entry(user_id: int,
                      day: date,
                      mood_score: Optional[int] = None,
                      text_note: Optional[str] = None) -> MoodEntry:
    """
    Создать или обновить запись настроения пользователя за день.
    Гарантирует одну запись настроения на (user_id, date).
    """
    with get_session() as db:
        entry = (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == user_id, MoodEntry.date == day)
            .first()
        )

        if entry:
            # обновляем существующую
            entry.mood_score = mood_score
            entry.text_note = text_note
        else:
            # создаём новую
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

