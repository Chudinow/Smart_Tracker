import streamlit as st
import requests
# Настройки
BACKEND_URL = "http://localhost:8000"  # Будет меняться на продакшене
st.set_page_config(page_title="Smart Habit Tracker", page_icon="📊")
st.title("📊 Smart Habit Tracker")
st.write("Добро пожаловать в трекер привычек с AI-анализом настроения!")
# Проверка связи с бэкендом
try:
    response = requests.get(f"{BACKEND_URL}/health")
    if response.status_code == 200:
        st.success("✅ Связь с сервером установлена")
    else:
        st.error("❌ Сервер не отвечает")
except:
    st.error("❌ Не удалось подключиться к серверу")
# Здесь потом будут формы для привычек
st.write("Скдесь будут формы для добавления привычек...")
