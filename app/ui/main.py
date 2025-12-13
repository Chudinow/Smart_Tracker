from fastapi import FastAPI, Request, Form, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import date
from pathlib import Path as PathlibPath
from app.db.init_db import init_db
from app.core.auth import register_user, authenticate_user  
from starlette.middleware.sessions import SessionMiddleware
from app.db.repo import get_daily_state_for_user, upsert_mood_entry, add_habit_log_safe, create_habit, archive_habit_for_user

app = FastAPI(title="Work Life Balance UI")

app.add_middleware(
    SessionMiddleware,
    secret_key="CHANGE_ME_TO_SOMETHING_RANDOM",  # потом вынеси в env
    session_cookie="wlb_session",
    same_site="lax",
    https_only=False,  # на проде True
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
    # чтобы таблицы точно были
    init_db()


@app.get("/", response_class=HTMLResponse)
async def root():
    # редирект просто на /login
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

    # Пока без настоящих сессий — просто простая страница "вы залогинились"
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

    # --- COUNTER: +1 ---
    if kind == "counter":
        cur_value = int(found.get("value") or 0)
        target = found.get("target")
        new_value = cur_value + 1
        completed = bool(target) and new_value >= int(target)
        add_habit_log_safe(habit_id=habit_id, day=today, completed=completed, value=new_value)
        return RedirectResponse("/app", status_code=303)

    # --- CHECKBOX: toggle completed ---
    cur_completed = bool(found.get("completed", False))
    add_habit_log_safe(habit_id=habit_id, day=today, completed=(not cur_completed), value=None)
    return RedirectResponse("/app", status_code=303)


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

@app.get("/history", response_class=HTMLResponse)
async def history_stub(request: Request):
    return HTMLResponse("История — в разработке")

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_stub(request: Request):
    return HTMLResponse("Аналитика — в разработке")

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


