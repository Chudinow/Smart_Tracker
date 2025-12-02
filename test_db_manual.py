# test_db_manual.py

from datetime import date

from app.db.init_db import init_db
from app.core.auth import register_user, authenticate_user
from app.db.repo import (
    create_habit,
    get_user_habits,
    add_habit_log_safe,
    get_logs_for_user,
    upsert_mood_entry,
    get_mood_entries,
    get_all_users,
)


def main():

    print("-------Все пользователи в БД-------")
    for user in get_all_users():
        print(" •", user)
    
    # --- Привычки ---
    print("\n=== ПРОВЕРКА ПРИВЫЧЕК ===")
    if not get_user_habits(user.id):
        print("Привычек нет, создаём тестовую...")
        create_habit(
            user_id=user.id,
            name="Тестовая привычка",
            description="Проверка сохранения в БД",
            frequency="ежедневно",
        )

    habits = get_user_habits(user.id)
    print(f"Найдено привычек: {len(habits)}")
    for h in habits:
        print(f"- Habit id={h.id}, name={h.name}")

    # Лог за сегодня для первой привычки
    today = date.today()
    first_habit = habits[0]
    add_habit_log_safe(
        habit_id=first_habit.id,
        day=today,
        completed=True,
    )

    logs_today = get_logs_for_user(user.id, start=today, end=today)
    print(f"\nЛоги за сегодня: {len(logs_today)}")
    for log in logs_today:
        print(
            f"- Log id={log.id}, habit_id={log.habit_id}, "
            f"date={log.date}, completed={log.completed}"
        )

    # --- Настроение ---
    print("\n=== ПРОВЕРКА НАСТРОЕНИЯ ===")
    upsert_mood_entry(
        user_id=user.id,
        day=today,
        mood_score=8,
        text_note="Тестовая запись настроения",
    )

    mood_entries = get_mood_entries(user.id, start=today, end=today)
    print(f"Записей настроения за сегодня: {len(mood_entries)}")
    for m in mood_entries:
        print(
            f"- MoodEntry id={m.id}, date={m.date}, score={m.mood_score}, "
            f"text={m.text_note!r}"
        )

    print("\nOK: всё успешно записалось в базу.")


if __name__ == "__main__":
    main()
