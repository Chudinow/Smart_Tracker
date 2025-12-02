from datetime import date
from app.db.repo import (create_user, create_habit, 
                        get_user_by_username, get_all_users, get_all_habits, 
                        get_user_habits, add_habit_log_safe, 
                        create_mood_entry, get_mood_entries,)


#.\.venv\Scripts\Activate.ps1
#python -m app.db.init_db
#python -m test


#---------ТЕСТ_1----------

USERNAME = "test_user_1"

print("-------Создаем 1 пользователя-------")
u1 = get_user_by_username(USERNAME)
if u1 is None:
    u1 = create_user(USERNAME, "hash123", "Эдуард")
    print("Создан новый пользователь:", u1)
else:
    print("Пользователь уже существует:", u1)

USERNAME = "test_user_2"

print("-------Создаем 2 пользователя-------")
u2 = get_user_by_username(USERNAME)
if u2 is None:
    u2 = create_user(USERNAME, "hash1234", "Эдуард")
    print("Создан новый пользователь:", u2)
else:
    print("Пользователь уже существует:", u2)

print("-------Создаём привычку-------")
h = create_habit(u1.id, "Спорт", "30 минут тренировок", "daily")
print("Создана привычка:", h)

print("-------Все пользователи в БД-------")
for user in get_all_users():
    print(" •", user)

print("-------Все привычки в БД-------")
for habit in get_all_habits():
    print(" •", habit)

#---------ТЕСТ_2----------
"""
USERNAME = "test_user_logs"
HABIT_NAME = "Спорт"

print("-------логирование привычки-------")

# Гарантируем, что пользователь существует
user = get_user_by_username(USERNAME)
if user is None:
    user = create_user(USERNAME, "hash123", "Тест логов")
    print("Создан пользователь:", user)
else:
    print("Пользователь уже существует:", user)

# Гарантируем, что у него есть нужная привычка
habits = get_user_habits(user.id)
habit = next((h for h in habits if h.name == HABIT_NAME), None)

if habit is None:
    habit = create_habit(
        user_id=user.id,
        name=HABIT_NAME,
        description="30 минут тренировок",
        frequency="daily",
    )
    print("Создана привычка:", habit)
else:
    print("Найдена существующая привычка:", habit)

# 3. Добавляем / обновляем лог на сегодня
log = add_habit_log_safe(
    habit_id=habit.id,
    day=date.today(),
    completed=True,
    value=30,
    note="Легкая тренировка",
)

print("Лог поведения:", log)
"""
#---------ТЕСТ_3----------

"""
#USERNAME_MOOD = "test_user_mood"
#
#print("----------дневник настроения----------")
#
## 1. Гарантируем, что пользователь существует
#user = get_user_by_username(USERNAME_MOOD)
#if user is None:
#    user = create_user(USERNAME_MOOD, "hash123", "Тест настроения")
#    print("Создан пользователь:", user)
#else:
#    print("Пользователь уже существует:", user)
#
## 2. Создаём новую запись настроения на сегодня
#m = create_mood_entry(
#    user_id=user.id,
#    day=date.today(),
#    mood_score=7,
#    text_note="Хороший день!",
#)
#
#print("Создана запись настроения:", m)
#
## 3. Показываем все записи настроения этого пользователя
#print("\nВсе записи настроения пользователя:")
#entries = get_mood_entries(user.id)
#for e in entries:
#    print(" •", e)
"""