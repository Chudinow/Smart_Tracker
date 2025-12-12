from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.init_db import init_db
from app.core.auth import register_user, authenticate_user  # твой текущий бек

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Work Life Balance UI")

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
    return templates.TemplateResponse(
        "login_success.html",
        {
            "request": request,
            "user": user,
        },
    )


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


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    display_name: str = Form(None),
):
    if password != password2:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Пароли не совпадают",
            },
            status_code=400,
        )

    try:
        register_user(
            username=username,
            password=password,
            display_name=display_name,
        )
    except ValueError as e:
        # например "Пользователь с таким логином уже существует"
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": str(e),
            },
            status_code=400,
        )

    # Успешная регистрация — отправляем на /login с флажком
    return RedirectResponse("/login?registered=1", status_code=303)
