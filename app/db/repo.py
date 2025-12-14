# app/db/repo.py
from typing import Optional
from datetime import date, datetime, timedelta
from sqlalchemy.exc import IntegrityError
from .connection import get_session
from .models import User, Habit, HabitLog, MoodEntry
from sqlalchemy import func
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

def get_mood_entry(user_id: int, day: date) -> Optional[MoodEntry]:
    with get_session() as db:
        return (
            db.query(MoodEntry)
            .filter(MoodEntry.user_id == user_id, MoodEntry.date == day)
            .first()
        )
    
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

def get_month_overview(user_id: int, start: date, end: date) -> dict[date, dict]:
    with get_session() as db:
        habits = (
            db.query(Habit.id, Habit.kind, Habit.target)
            .filter(Habit.user_id == user_id, Habit.is_active == True)
            .all()
        )
        habits_map = {h.id: (h.kind, int(h.target) if h.target else None) for h in habits}
        total_habits = len(habits)

        logs = (
            db.query(HabitLog.habit_id, HabitLog.date, HabitLog.value, HabitLog.completed)
            .join(Habit, Habit.id == HabitLog.habit_id)
            .filter(
                Habit.user_id == user_id,
                Habit.is_active == True,
                HabitLog.date >= start,
                HabitLog.date <= end,
            )
            .all()
        )

        # day -> habit_id -> max_progress(0..1)
        day_habit_max = defaultdict(dict)
        by_day_any = set()

        for habit_id, d, value, completed in logs:
            by_day_any.add(d)
            kind, target = habits_map.get(habit_id, ("checkbox", None))

            if kind == "counter" and target:
                v = int(value or 0)
                progress = min(v / target, 1.0)
            else:
                progress = 1.0 if completed else 0.0

            prev = day_habit_max[d].get(habit_id, 0.0)
            if progress > prev:
                day_habit_max[d][habit_id] = progress

        moods = (
            db.query(MoodEntry.date, MoodEntry.mood_score, MoodEntry.text_note)
            .filter(
                MoodEntry.user_id == user_id,
                MoodEntry.date >= start,
                MoodEntry.date <= end,
            )
            .all()
        )
        mood_by_day = {d: {"score": s, "note": (t or "")} for d, s, t in moods}

        result = {}
        d = start
        while d <= end:
            has_mood = d in mood_by_day
            has_any = (d in by_day_any) or has_mood

            # суммарный прогресс дня = сумма максимумов по привычкам
            s = sum(day_habit_max.get(d, {}).values())
            percent = int((s / total_habits) * 100) if total_habits > 0 else 0
            percent = max(0, min(100, percent))  # на всякий

            mood_score = mood_by_day.get(d, {}).get("score", None)
            mood_note = mood_by_day.get(d, {}).get("note", "")

            result[d] = {
                "has_data": has_any,
                "percent": percent,
                "mood_score": mood_score,
                "has_note": bool(mood_note.strip()),
                "warn": has_any and total_habits > 0 and percent < 100,
            }
            d += timedelta(days=1)

        return result
    
def _habit_progress(kind: str, target: int | None, value: int | None, completed: bool) -> float:
    """Прогресс по одной записи лога в диапазоне 0..1"""
    if kind == "counter" and target and target > 0:
        v = int(value or 0)
        return min(v / target, 1.0)
    return 1.0 if completed else 0.0


def get_analytics_summary(user_id: int, start: date, end: date) -> dict:
    """
    MVP-аналитика на период:
    - среднее настроение
    - лучший/худший день
    - % выполнения (по активным привычкам)
    - "главная привычка" (самая выполненная за период)
    - данные для простого графика настроения
    """
    with get_session() as db:
        # активные привычки
        habits = (
            db.query(Habit.id, Habit.name, Habit.kind, Habit.target)
            .filter(Habit.user_id == user_id, Habit.is_active == True)
            .all()
        )
        habits_map = {h.id: {"name": h.name, "kind": h.kind, "target": int(h.target) if h.target else None} for h in habits}
        habit_ids = list(habits_map.keys())

        days = []
        cur = start
        while cur <= end:
            days.append(cur)
            cur += timedelta(days=1)

        # логи привычек за период (ТОЛЬКО активные привычки)
        logs = []
        if habit_ids:
            logs = (
                db.query(HabitLog.habit_id, HabitLog.date, HabitLog.value, HabitLog.completed)
                .join(Habit, Habit.id == HabitLog.habit_id)
                .filter(
                    Habit.user_id == user_id,
                    Habit.is_active == True,
                    HabitLog.date >= start,
                    HabitLog.date <= end,
                )
                .all()
            )

        # day -> habit_id -> max_progress
        day_habit_max = defaultdict(dict)
        for habit_id, d, value, completed in logs:
            meta = habits_map.get(habit_id)
            if not meta:
                continue
            progress = _habit_progress(meta["kind"], meta["target"], value, completed)
            prev = day_habit_max[d].get(habit_id, 0.0)
            if progress > prev:
                day_habit_max[d][habit_id] = progress

        total_possible = len(days) * max(len(habit_ids), 1)
        total_done = 0.0

        # для "главной привычки"
        habit_sum = defaultdict(float)

        for d in days:
            for hid in habit_ids:
                p = day_habit_max[d].get(hid, 0.0)
                total_done += p
                habit_sum[hid] += p

        completion_percent = 0
        if habit_ids and total_possible > 0:
            completion_percent = int(round((total_done / (len(days) * len(habit_ids))) * 100))

        top_habit = None
        if habit_ids:
            top_id = max(habit_ids, key=lambda hid: habit_sum.get(hid, 0.0))
            top_habit = {
                "name": habits_map[top_id]["name"],
                "score": habit_sum.get(top_id, 0.0),   # сумма прогресса за период
                "max": float(len(days)),               # максимум (если каждый день 1.0)
            }

        # настроение
        mood_entries = (
            db.query(MoodEntry.date, MoodEntry.mood_score)
            .filter(
                MoodEntry.user_id == user_id,
                MoodEntry.date >= start,
                MoodEntry.date <= end,
            )
            .order_by(MoodEntry.date)
            .all()
        )

        mood_by_day = {d: s for d, s in mood_entries if s is not None}

        scores = [s for s in mood_by_day.values() if s is not None]
        avg_mood = round(sum(scores) / len(scores), 2) if scores else None

        best_day = None
        worst_day = None
        if scores:
            best_date = max(mood_by_day.keys(), key=lambda d: mood_by_day[d])
            worst_date = min(mood_by_day.keys(), key=lambda d: mood_by_day[d])
            best_day = {"date": best_date, "score": mood_by_day[best_date]}
            worst_day = {"date": worst_date, "score": mood_by_day[worst_date]}

        # серия для графика настроения (по всем дням периода)
        mood_series = [{"date": d, "score": mood_by_day.get(d)} for d in days]

        return {
            "start": start,
            "end": end,
            "days_count": len(days),
            "habits_count": len(habit_ids),
            "completion_percent": completion_percent,
            "top_habit": top_habit,
            "avg_mood": avg_mood,
            "best_day": best_day,
            "worst_day": worst_day,
            "mood_series": mood_series,
        }

def get_habits_breakdown(user_id: int, start: date, end: date) -> list[dict]:
    """
    Разбор по привычкам за период без серий:
    - percent: средний прогресс (0..100)
    - done: выполнено (для checkbox: дней; для counter: суммарно/цель)
    - misses: пропуски (дни с прогрессом 0)
    - avg: среднее в день (для counter: avg/target)
    """
    with get_session() as db:
        habits = (
            db.query(Habit.id, Habit.name, Habit.kind, Habit.target)
            .filter(Habit.user_id == user_id, Habit.is_active == True)
            .all()
        )
        if not habits:
            return []

        days_count = (end - start).days + 1
        habit_ids = [h.id for h in habits]
        habits_map = {
            h.id: {
                "name": h.name,
                "kind": h.kind or "counter",
                "target": int(h.target) if h.target else None,
            }
            for h in habits
        }

        logs = (
            db.query(HabitLog.habit_id, HabitLog.date, HabitLog.value, HabitLog.completed)
            .join(Habit, Habit.id == HabitLog.habit_id)
            .filter(
                Habit.user_id == user_id,
                Habit.is_active == True,
                HabitLog.date >= start,
                HabitLog.date <= end,
                HabitLog.habit_id.in_(habit_ids),
            )
            .all()
        )

        # habit_id -> date -> (value, completed)
        by_habit_day = defaultdict(dict)
        for hid, d, value, completed in logs:
            by_habit_day[hid][d] = (int(value or 0), bool(completed))

        result = []

        for hid in habit_ids:
            meta = habits_map[hid]
            kind = meta["kind"]
            target = meta["target"]

            progress_sum = 0.0
            done_days = 0
            misses = 0
            sum_value = 0

            best = {"date": None, "progress": -1.0}
            worst = {"date": None, "progress": 2.0}

            for i in range(days_count):
                d = start + timedelta(days=i)
                value, completed = by_habit_day[hid].get(d, (0, False))

                p = _habit_progress(kind, target, value, completed)  # 0..1
                progress_sum += p

                if p >= 1.0:
                    done_days += 1
                if p <= 0.0:
                    misses += 1

                if kind == "counter":
                    sum_value += int(value or 0)

                if p > best["progress"]:
                    best = {"date": d, "progress": p}
                if p < worst["progress"]:
                    worst = {"date": d, "progress": p}

            percent = int(round((progress_sum / max(days_count, 1)) * 100))
            percent = max(0, min(100, percent))

            if kind == "counter" and target and target > 0:
                goal_total = days_count * target
                done_text = f"{sum_value}/{goal_total}"
                avg_per_day = round(sum_value / max(days_count, 1), 1)
                avg_text = f"{avg_per_day}/{target}"
            else:
                done_text = f"{done_days}/{days_count}"
                avg_text = None

            result.append(
                {
                    "id": hid,
                    "name": meta["name"],
                    "kind": kind,
                    "target": target,
                    "percent": percent,
                    "done_text": done_text,
                    "misses": misses,
                    "avg_text": avg_text,
                    "best_date": best["date"],
                    "worst_date": worst["date"],
                }
            )

        # сортировка: по выполнению (по убыванию)
        result.sort(key=lambda x: x["percent"], reverse=True)
        return result

def get_mood_breakdown(user_id: int, start: date, end: date) -> dict:
    """
    Настроение за период:
    - avg: среднее
    - best/worst: лучший/худший день (дата, score, note)
    - dist: распределение 1-3 / 4-6 / 7-10
    - notes: заметки (дата, score, note) — последние 10
    """
    with get_session() as db:
        rows = (
            db.query(MoodEntry.date, MoodEntry.mood_score, MoodEntry.text_note)
            .filter(
                MoodEntry.user_id == user_id,
                MoodEntry.date >= start,
                MoodEntry.date <= end,
            )
            .order_by(MoodEntry.date)
            .all()
        )

        # только дни, где есть оценка
        scored = [(d, int(s), (t or "")) for d, s, t in rows if s is not None]
        scores = [s for _, s, _ in scored]

        avg = round(sum(scores) / len(scores), 2) if scores else None

        best = None
        worst = None
        if scored:
            best_d, best_s, best_t = max(scored, key=lambda x: x[1])
            worst_d, worst_s, worst_t = min(scored, key=lambda x: x[1])
            best = {"date": best_d, "score": best_s, "note": best_t}
            worst = {"date": worst_d, "score": worst_s, "note": worst_t}

        low = sum(1 for s in scores if 1 <= s <= 3)
        mid = sum(1 for s in scores if 4 <= s <= 6)
        high = sum(1 for s in scores if 7 <= s <= 10)
        total = len(scores)

        # заметки (берём только непустые, показываем свежие)
        notes = []
        for d, s, t in reversed(scored):
            if t.strip():
                notes.append({"date": d, "score": s, "note": t})
            if len(notes) >= 10:
                break

        return {
            "avg": avg,
            "best": best,
            "worst": worst,
            "dist": {"low": low, "mid": mid, "high": high, "total": total},
            "notes": notes,
        }
