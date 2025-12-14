from typing import Optional
from passlib.context import CryptContext

from app.db.repo import get_user_by_username, create_user
from app.db.models import User
import re

USERNAME_RE = re.compile(r"^[a-z0-9_][a-z0-9_.-]{1,30}[a-z0-9_]$")  # 3..32, без тире на краях

# Используем pbkdf2_sha256 вместо bcrypt,
# у него нет ограничения 72 байта
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    """Захешировать пароль для хранения в БД."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверить пароль при логине."""
    return pwd_context.verify(plain_password, hashed_password)


def register_user(
    username: str,
    password: str,
    display_name: Optional[str] = None,
) -> User:
    """
    Регистрация нового пользователя.
    - проверяет, что username свободен
    - хеширует пароль
    - создаёт запись в БД
    """
    username = (username or "").strip().lower()
    display_name = (display_name or "").strip() or None

    if not USERNAME_RE.match(username):
        raise ValueError("Логин: 3–32 символа, латиница/цифры, можно _.- (без спецсимволов)")

    if display_name is not None and len(display_name) > 40:
        raise ValueError("Имя: максимум 40 символов")
    
    existing = get_user_by_username(username)
    if existing is not None:
        raise ValueError("Пользователь с таким логином уже существует")

    password = password or ""
    if len(password) < 8:
        raise ValueError("Пароль: минимум 8 символов")

    if password.strip() != password:
        raise ValueError("Пароль не должен начинаться/заканчиваться пробелами")

    if password.lower() == username:
        raise ValueError("Пароль не должен совпадать с логином")
    
    password_hash = hash_password(password)
    user = create_user(
        username=username,
        password_hash=password_hash,
        display_name=display_name,
    )
    return user


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Проверка логина и пароля.
    Возвращает User при успехе, None — при неудаче.
    """
    user = get_user_by_username(username)
    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
