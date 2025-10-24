from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Smart Habit Tracker API")
# Разрешаем запросы от фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для продакшена нужно указать конкретный URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def root():
    return {"message": "Hello from Smart Habit Tracker API!"}
@app.get("/health")
async def health_check():
    return {"status": "OK"}
