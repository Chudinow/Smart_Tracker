from fastapi import FastAPI, Request, Form, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta
from pathlib import Path as PathlibPath
from app.db.init_db import init_db
from app.core.auth import register_user, authenticate_user  
from starlette.middleware.sessions import SessionMiddleware
from app.db.repo import get_daily_state_for_user, upsert_mood_entry, add_habit_log_safe, create_habit, archive_habit_for_user, get_mood_entry, get_month_overview, get_analytics_summary, get_habits_breakdown, get_mood_breakdown
import calendar
from fastapi import Query

app = FastAPI(title="Work Life Balance UI")

app.add_middleware(
    SessionMiddleware,
    secret_key="CHANGE_ME_TO_SOMETHING_RANDOM",  
    session_cookie="wlb_session",
    same_site="lax",
    https_only=False,  
)

BASE_DIR = PathlibPath(__file__).resolve().parent

RU_MONTHS = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
RU_WEEKDAYS = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]

def human_ru(d: date) -> str:
    return f"{d.day} {RU_MONTHS[d.month-1]}, {RU_WEEKDAYS[d.weekday()]}"

# Подключаем статику и шаблоны
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/login")


# ---------- ВХОД ----------

@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    error: str | None = None,
    registered: int | None = None,
):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error,
            "registered": registered,
        },
    )


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(username, password)
    if not user:
        # показываем ошибку на той же странице
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Неверный логин или пароль",
                "registered": None,
            },
            status_code=400,
        )

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse("/app", status_code=303)


# ---------- РЕГИСТРАЦИЯ ----------

@app.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    error: str | None = None,
):
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "error": error,
        },
    )

@app.get("/app", response_class=HTMLResponse)
async def app_home(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    today = date.today()

    habits_raw = get_daily_state_for_user(user_id=user_id, day=today)
    mood_today = get_mood_entry(user_id=user_id, day=today)

    mood_score = mood_today.mood_score if mood_today else None
    mood_note = mood_today.text_note if mood_today else ""

    habits = []
    for h in habits_raw:
        value = int(h.get("value") or 0)
        target = h.get("target")
    
        percent = 0
        if target and int(target) > 0:
            percent = int(min(100, (value / int(target)) * 100))
    
        habits.append({
            "id": h.get("habit_id"),
            "name": h.get("habit_name") or "Без названия",
            "description": h.get("description") or "",
            "frequency": h.get("frequency") or "",
            "kind": h.get("kind") or "counter",
            "value": value,
            "target": target,
            "percent": percent,
            "completed": bool(h.get("completed", False)),
        })
        
    habits_todo = [h for h in habits if not h["completed"]]
    habits_done = [h for h in habits if h["completed"]]
    flash_error = request.session.pop("flash_error", None)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "username": request.session.get("username", "user"),
            "date_human": human_ru(today),
            "habits_todo": habits_todo,
            "habits_done": habits_done,
            "flash_error": flash_error,
            "mood_score": mood_score,
            "mood_note": mood_note,
            "mood_emoji": mood_emoji(mood_score),
            "insight": None,
        },
    )

@app.post("/habit/{habit_id}/log")
async def habit_action(request: Request, habit_id: int = Path(...)):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    today = date.today()
    habits_raw = get_daily_state_for_user(user_id=user_id, day=today)

    found = None
    habits_by_id = {h.get("habit_id"): h for h in habits_raw}
    found = habits_by_id.get(habit_id)
    if not found:
        return RedirectResponse("/app", status_code=303)

    kind = found.get("kind") or "counter"

    if kind == "counter":
        cur_value = int(found.get("value") or 0)
        target = found.get("target")
        new_value = cur_value + 1
        completed = bool(target) and new_value >= int(target)
        add_habit_log_safe(habit_id=habit_id, day=today, completed=completed, value=new_value)
        return RedirectResponse("/app", status_code=303)

    cur_completed = bool(found.get("completed", False))
    add_habit_log_safe(habit_id=habit_id, day=today, completed=(not cur_completed), value=None)
    return RedirectResponse("/app", status_code=303)

def mood_emoji(score: int | None) -> str:
    if score is None:
        return "🙂"
    if score <= 2:
        return "😫"
    if score <= 4:
        return "😕"
    if score <= 6:
        return "😐"
    if score <= 8:
        return "🙂"
    if score == 9:
        return "😄"
    return "🤩"


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    display_name: str | None = Form(None),
):
    if password != password2:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Пароли не совпадают",
                "prefill_username": username,
                "prefill_display_name": display_name,
            },
            status_code=400,
        )

    try:
        user = register_user(
            username=username,
            password=password,
            display_name=display_name,
        )

        request.session["user_id"] = user.id
        request.session["username"] = user.username
    except ValueError as e:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": str(e),
                "prefill_username": username,
                "prefill_display_name": display_name,
            },
            status_code=400,
        )

    return RedirectResponse("/app", status_code=303)

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    period: int = Query(7),
    tab: str = Query("stats"),
):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    username = request.session.get("username", "user")

    # нормализуем period и tab
    if period not in (7, 30, 90):
        period = 7
    if tab not in ("stats", "habits", "mood"):
        tab = "stats"

    end = date.today()
    start = end - timedelta(days=period - 1)

    summary = get_analytics_summary(user_id=user_id, start=start, end=end)
    habits_breakdown = get_habits_breakdown(user_id=user_id, start=start, end=end) if tab == "habits" else []

    mood_breakdown = get_mood_breakdown(user_id=user_id, start=start, end=end) if tab == "mood" else None

    if mood_breakdown:
        if mood_breakdown.get("best"):
            mood_breakdown["best"]["emoji"] = mood_emoji(mood_breakdown["best"]["score"])
        if mood_breakdown.get("worst"):
            mood_breakdown["worst"]["emoji"] = mood_emoji(mood_breakdown["worst"]["score"])
        for n in mood_breakdown.get("notes", []):
            n["emoji"] = mood_emoji(n["score"])

    # --- ГРАФИК НАСТРОЕНИЯ: сегменты + точки + подписи осей ---
    series = summary["mood_series"]

    import math
    W, H = 640, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 34, 10, 10, 18
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    n = len(series)

    def xy(i: int, score: int):
        x = PAD_L + (i * plot_w / max(n - 1, 1))
        y = PAD_T + plot_h - ((score - 1) / 9) * plot_h
        return x, y

    mood_segments: list[str] = []
    mood_points: list[dict] = []
    cur_seg: list[str] = []

    for i, it in enumerate(series):
        d = it["date"]
        score = it["score"]
        if score is None:
            if cur_seg:
                mood_segments.append(" ".join(cur_seg))
                cur_seg = []
            continue

        x, y = xy(i, int(score))
        cur_seg.append(f"{x:.1f},{y:.1f}")
        mood_points.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "date_full": d.strftime("%d.%m.%Y"),
                "score": int(score),
            }
        )

    if cur_seg:
        mood_segments.append(" ".join(cur_seg))

    # подписи по Y (10..2)
    mood_y_ticks = []
    for val in (10, 8, 6, 4, 2):
        _, y = xy(0, val)
        mood_y_ticks.append({"val": val, "y": round(y, 1)})

    # подписи по X — ~7 штук
    mood_x_ticks = []
    if n > 0:
        max_labels = 7
        step = 1 if n <= max_labels else math.ceil((n - 1) / (max_labels - 1))
        idxs = list(range(0, n, step))
        if (n - 1) not in idxs:
            idxs.append(n - 1)
        for i in idxs:
            d = series[i]["date"]
            x = PAD_L + (i * plot_w / max(n - 1, 1))
            mood_x_ticks.append({"x": round(x, 1), "label": d.strftime("%d.%m")})

    mood_chart = {
        "w": W, "h": H,
        "pad_l": PAD_L, "pad_r": PAD_R, "pad_t": PAD_T, "pad_b": PAD_B,
        "x1": PAD_L, "x2": W - PAD_R,
        "y_bottom": H - PAD_B,
    }

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "username": username,

            "period": period,
            "tab": tab,

            "mood_breakdown": mood_breakdown,
            "habits_breakdown": habits_breakdown,
            "summary": summary,
            "mood_segments": mood_segments,
            "mood_points": mood_points,
            "mood_y_ticks": mood_y_ticks,
            "mood_x_ticks": mood_x_ticks,
            "mood_chart": mood_chart,
        },
    )

@app.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    day: int | None = Query(default=None),
):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    today = date.today()

    y = year or today.year
    m = month or today.month

    # выбранный день (если не передан — сегодня, но в рамках текущего месяца)
    try:
        selected = date(y, m, day) if day else date(y, m, min(today.day, calendar.monthrange(y, m)[1]))
    except ValueError:
        selected = date(y, m, 1)

    first_day = date(y, m, 1)
    last_day = date(y, m, calendar.monthrange(y, m)[1])

    overview = get_month_overview(user_id=user_id, start=first_day, end=last_day)

    # календарная сетка (недели)
    cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
    weeks = []
    for week in cal.monthdatescalendar(y, m):
        row = []
        for d in week:
            in_month = (d.month == m)
            info = overview.get(d, {"has_data": False, "percent": 0, "mood_score": None, "has_note": False, "warn": False, "fire": False})
            row.append({
                "date": d,
                "day": d.day,
                "in_month": in_month,
                "is_today": (d == today),
                "is_selected": (d == selected),
                **info
            })
        weeks.append(row)

    # правая панель: детали выбранного дня (пока просто просмотр)
    habits_raw = get_daily_state_for_user(user_id=user_id, day=selected)
    mood_today = get_mood_entry(user_id=user_id, day=selected)

    habits = []
    for h in habits_raw:
        value = int(h.get("value") or 0)
        target = h.get("target")
        percent = 0
        if target and int(target) > 0:
            percent = int(min(100, (value / int(target)) * 100))

        habits.append({
            "id": h.get("habit_id"),
            "name": h.get("habit_name") or "Без названия",
            "frequency": h.get("frequency") or "",
            "kind": h.get("kind") or "counter",
            "value": value,
            "target": target,
            "percent": percent,
            "completed": bool(h.get("completed", False)),
        })

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "username": request.session.get("username", "user"),
            "month_title": f"{RU_MONTHS[m-1].capitalize()} {y}",
            "weeks": weeks,
            "selected_date": selected,
            "selected_human": human_ru(selected),
            "mood_score": (mood_today.mood_score if mood_today else None),
            "mood_note": (mood_today.text_note if mood_today else ""),
            "mood_emoji": mood_emoji(mood_today.mood_score if mood_today else None),
            "habits": habits,
            "prev_link": f"/history?year={(first_day - timedelta(days=1)).year}&month={(first_day - timedelta(days=1)).month}",
            "next_link": f"/history?year={(last_day + timedelta(days=1)).year}&month={(last_day + timedelta(days=1)).month}",
            "today_link": f"/history?year={today.year}&month={today.month}&day={today.day}",
        },
    )

@app.post("/habit/{habit_id}/dec")
async def habit_decrement(request: Request, habit_id: int = Path(...)):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    today = date.today()
    habits_raw = get_daily_state_for_user(user_id=user_id, day=today)
    habits_by_id = {h.get("habit_id"): h for h in habits_raw}
    found = habits_by_id.get(habit_id)
    if not found:
        return RedirectResponse("/app", status_code=303)

    kind = found.get("kind") or "counter"
    if kind != "counter":
        return RedirectResponse("/app", status_code=303)

    cur_value = int(found.get("value") or 0)
    target = found.get("target")
    new_value = max(0, cur_value - 1)

    completed = False
    if target and int(target) > 0:
        completed = new_value >= int(target)

    add_habit_log_safe(habit_id=habit_id, day=today, completed=completed, value=new_value)
    return RedirectResponse("/app", status_code=303)

@app.post("/habit/{habit_id}/archive")
async def habit_archive(request: Request, habit_id: int = Path(...)):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    ok = archive_habit_for_user(user_id=user_id, habit_id=habit_id)
    if not ok:
        request.session["flash_error"] = "Не удалось архивировать привычку."
    return RedirectResponse("/app", status_code=303)

@app.post("/habit/new")
async def new_habit(
    request: Request,
    name: str = Form(...),
    kind: str = Form("counter"),
    target: int | None = Form(None),
    frequency: str = Form(""),
):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    name = name.strip()
    frequency = frequency.strip() or None

    if kind not in ("counter", "checkbox"):
        kind = "counter"

    if kind == "checkbox":
        target = None
    else:
        if target is None or int(target) < 1:
            request.session["flash_error"] = "Для счётчика нужно указать цель (минимум 1)."
            return RedirectResponse("/app", status_code=303)

    create_habit(
        user_id=user_id,
        name=name,
        description=None,
        frequency=frequency,
        kind=kind,
        target=target,
    )
    return RedirectResponse("/app", status_code=303)

@app.post("/mood")
async def save_mood(
    request: Request,
    mood: int = Form(...),
    note: str = Form(""),
):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)

    user_id = request.session["user_id"]
    today = date.today()

    upsert_mood_entry(user_id=user_id, day=today, mood_score=mood, text_note=note)
    return RedirectResponse("/app", status_code=303)


