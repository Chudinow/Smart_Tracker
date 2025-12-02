# streamlit_app.py

import streamlit as st
from datetime import date, timedelta

from app.db.init_db import init_db
from app.db.repo import (
    get_user_habits,
    create_habit,
    get_logs_for_user,
    add_habit_log_safe,
    upsert_mood_entry,
    get_mood_entries,
)
from app.core.auth import register_user, authenticate_user


# --- ИНИЦИАЛИЗАЦИЯ БД ПРИ СТАРТЕ ---
init_db()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ UI ---

def get_daily_state_for_user(user_id: int, day: date):
    """
    Вернуть список привычек пользователя + их состояние на конкретный день.
    Использует существующие функции репозитория.
    """
    habits = get_user_habits(user_id)
    logs = get_logs_for_user(user_id, start=day, end=day)
    logs_by_habit_id = {log.habit_id: log for log in logs}

    result = []
    for h in habits:
        log = logs_by_habit_id.get(h.id)
        result.append(
            {
                "habit_id": h.id,
                "habit_name": h.name,
                "description": h.description,
                "completed": bool(log.completed) if log else False,
                "value": log.value if log else None,
            }
        )
    return result


def get_mood_last_days(user_id: int, days: int = 7):
    """Получить записи настроения за последние N дней (для истории)."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    return get_mood_entries(user_id, start=start, end=end)


# --- НАСТРОЙКА СЕССИИ ---

if "user" not in st.session_state:
    st.session_state.user = None  # сюда будем класть объект User из БД


# --- САЙДБАР: ЛОГИН / РЕГИСТРАЦИЯ ---

st.sidebar.title("Smart Habit Tracker")

mode = st.sidebar.radio("Режим", ["Вход", "Регистрация"], horizontal=True)

if mode == "Вход":
    st.sidebar.subheader("Вход")
else:
    st.sidebar.subheader("Регистрация")

# ЛОГИН
username = st.sidebar.text_input(
    "Логин",
    max_chars=32,
    help="От 3 до 20 символов, только буквы и цифры",
)

if mode == "Вход":
    # Простой вход
    password = st.sidebar.text_input("Пароль", type="password", key="login_password")
    password_confirm = None
    display_name = None
else:
    # Регистрация
    display_name = st.sidebar.text_input(
        "Отображаемое имя",
        help="Будет видно в интерфейсе",
    )
    password = st.sidebar.text_input("Пароль", type="password", key="reg_password")
    password_confirm = st.sidebar.text_input(
        "Повторите пароль", type="password", key="reg_password_confirm"
    )

if st.sidebar.button("Продолжить"):
    # --- РЕГИСТРАЦИЯ ---
    if mode == "Регистрация":
        errors: list[str] = []

        # Валидация логина
        if not username:
            errors.append("Введите логин.")
        elif not (3 <= len(username) <= 20):
            errors.append("Логин должен быть от 3 до 20 символов.")
        elif not username.isalnum():
            errors.append("Логин может содержать только буквы и цифры (a–z, 0–9).")

        # Валидация пароля
        if not password or not password_confirm:
            errors.append("Введите пароль и его подтверждение.")
        elif len(password) < 6:
            errors.append("Пароль должен быть не короче 6 символов.")
        elif password != password_confirm:
            errors.append("Пароли не совпадают.")

        if errors:
            for msg in errors:
                st.sidebar.error(msg)
        else:
            try:
                user = register_user(username, password, display_name)
                st.session_state.user = user
                st.sidebar.success("Регистрация успешна, вы вошли")
            except ValueError as e:
                # Например: "Пользователь с таким логином уже существует"
                st.sidebar.error(str(e))

    # --- ВХОД ---
    else:
        if not username or not password:
            st.sidebar.error("Введите логин и пароль.")
        else:
            user = authenticate_user(username, password)
            if user is None:
                st.sidebar.error("Неверный логин или пароль")
            else:
                st.session_state.user = user
                st.sidebar.success(f"Привет, {user.display_name or user.username}!")



if st.session_state.user:
    st.sidebar.write("---")
    st.sidebar.write(f"Текущий пользователь: **{st.session_state.user.username}**")
    if st.sidebar.button("Выйти"):
        st.session_state.user = None


# --- ОСНОВНОЕ СОДЕРЖИМОЕ ---

st.title("Smart Habit & Mood Tracker")

if not st.session_state.user:
    st.info("Войдите или зарегистрируйтесь через панель слева, чтобы продолжить.")
    st.stop()

user = st.session_state.user
st.write(f"Вы вошли как **{user.display_name or user.username}**")


tab1, tab2, tab3 = st.tabs(["Привычки на сегодня", "Добавить привычку", "Настроение"])


# --- ТАБ 1: ПРИВЫЧКИ НА СЕГОДНЯ ---

with tab1:
    st.subheader("Привычки на сегодня")

    today = date.today()
    daily_state = get_daily_state_for_user(user.id, today)

    if not daily_state:
        st.warning("У вас пока нет привычек. Добавьте их на соседней вкладке.")
    else:
        for item in daily_state:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{item['habit_name']}**")
                if item["description"]:
                    st.caption(item["description"])
            with col2:
                completed = st.checkbox(
                    "Выполнено",
                    value=item["completed"],
                    key=f"completed_{item['habit_id']}",
                )
            with col3:
                if st.button("Сохранить", key=f"save_{item['habit_id']}"):
                    add_habit_log_safe(
                        habit_id=item["habit_id"],
                        day=today,
                        completed=completed,
                    )
                    st.success("Статус сохранён")
                    st.rerun()


# --- ТАБ 2: ДОБАВЛЕНИЕ НОВОЙ ПРИВЫЧКИ ---

with tab2:
    st.subheader("Добавить привычку")

    new_habit_name = st.text_input("Название привычки", key="new_habit_name")
    new_habit_descr = st.text_area("Описание", key="new_habit_descr")
    new_habit_freq = st.text_input("Частота (например: каждый день)", key="new_habit_freq")

    if st.button("Создать привычку"):
        if not new_habit_name:
            st.error("Название привычки обязательно")
        else:
            create_habit(
                user_id=user.id,
                name=new_habit_name,
                description=new_habit_descr or None,
                frequency=new_habit_freq or None,
            )
            st.success("Привычка создана")
            st.rerun()


# --- ТАБ 3: НАСТРОЕНИЕ ---

with tab3:
    st.subheader("Настроение за сегодня")

    mood_score = st.slider("Оцените своё настроение", min_value=1, max_value=10, value=7)
    mood_note = st.text_area("Комментарий / дневник", height=100)

    if st.button("Сохранить настроение за сегодня"):
        upsert_mood_entry(
            user_id=user.id,
            day=date.today(),
            mood_score=mood_score,
            text_note=mood_note or None,
        )
        st.success("Настроение сохранено")

    st.markdown("---")
    st.subheader("История настроения (последние 7 дней)")

    entries = get_mood_last_days(user.id, days=7)
    if not entries:
        st.info("Пока нет записей настроения.")
    else:
        # Покажем таблицу: дата, оценка, короткая заметка
        data = [
            {
                "Дата": e.date,
                "Оценка": e.mood_score,
                "Текст": (e.text_note[:40] + "…") if e.text_note and len(e.text_note) > 40 else e.text_note,
            }
            for e in entries
        ]
        st.table(data)
