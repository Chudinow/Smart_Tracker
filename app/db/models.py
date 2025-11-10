# app/db/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
import datetime

# Берём Base из connection
from .connection import Base

# ---------- User ----------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=True) # Отображаемое имя
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # relationship
    habits = relationship("Habit", back_populates="owner", cascade="all, delete-orphan")
    mood_entries = relationship("MoodEntry", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} username={self.username}>"

# ---------- Habit ----------
class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(String, nullable=True)   # Как часто выполняется привычка
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False) # Отключение привычки (архив)

    owner = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Habit id={self.id} name={self.name} user_id={self.user_id}>"

# ---------- HabitLog / HabitEntry ----------
class HabitLog(Base):
    __tablename__ = "habit_logs"
    # Уникальность по (habit_id, date) предотвращает создание двух логов за один день для одной привычки
    __table_args__ = (
        UniqueConstraint('habit_id', 'date', name='uq_habit_date'),
        Index('ix_habitlogs_user_habit_date', 'user_id', 'habit_id', 'date'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    habit_id = Column(Integer, ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)        # Дата выполнения, только день
    completed = Column(Boolean, default=False, nullable=False)
    value = Column(Integer, nullable=True)    # Например количество минут/повторов
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    habit = relationship("Habit", back_populates="logs")

    def __repr__(self):
        return f"<HabitLog id={self.id} habit_id={self.habit_id} date={self.date} completed={self.completed}>"

# ---------- MoodEntry ----------
class MoodEntry(Base):
    __tablename__ = "mood_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)               # день, к которому относится настроение
    mood_score = Column(Integer, nullable=True)       # например 1..10 или None
    text_note = Column(Text, nullable=True)
    sentiment_label = Column(String, nullable=True)   # positive/neutral/negative
    sentiment_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="mood_entries")

    def __repr__(self):
        return f"<MoodEntry id={self.id} user_id={self.user_id} date={self.date} score={self.mood_score}>"
