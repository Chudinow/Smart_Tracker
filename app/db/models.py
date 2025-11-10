from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    habits = relationship("Habit", back_populates="owner", cascade="all, delete-orphan")
    mood_entries = relationship("MoodEntry", back_populates="owner", cascade="all, delete-orphan")

class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(String, nullable=True)  # например "daily", "3/week" и т.д.
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

    owner = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")

class HabitLog(Base):
    __tablename__ = "habit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    completed = Column(Boolean, default=False)
    value = Column(Integer, nullable=True)  # количество минут/повторов и т.п.
    note = Column(Text, nullable=True)

    habit = relationship("Habit", back_populates="logs")

class MoodEntry(Base):
    __tablename__ = "mood_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    mood_score = Column(Integer, nullable=True)   # 1..10 или None
    text_note = Column(Text, nullable=True)
    sentiment_label = Column(String, nullable=True)   # positive/neutral/negative
    sentiment_confidence = Column(Float, nullable=True)

    owner = relationship("User", back_populates="mood_entries")
