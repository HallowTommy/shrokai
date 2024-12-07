import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database
from gtts import gTTS
import requests

# --- Логирование ---
logging.basicConfig(level=logging.INFO)

# --- Database setup ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:OyusRvnLIzSfEvBSchmDxHKwHjjLwzPd@postgres.railway.internal:5432/railway"
)
if not DATABASE_URL:
    raise ValueError("Переменная окружения DATABASE_URL не найдена")

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = Database(DATABASE_URL)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    text = Column(Text)

Base.metadata.create_all(bind=engine)

# --- Chat application ---
app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info("New WebSocket connection established.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logging.info("WebSocket connection closed.")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.on_event("startup")
async def startup():
    logging.info("Connecting to the database...")
    await db.connect()
    logging.info("Database connection established.")

@app.on_event("shutdown")
async def shutdown():
    logging.info("Disconnecting from the database...")
    await db.disconnect()
    logging.info("Database connection closed.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            username = data.get("username")
            text = data.get("text")

            if not username or not text:
                await websocket.send_json({"error": "Username and text are required"})
                continue

            # Save to database
            query = Message.__table__.insert().values(username=username, text=text)
            await db.execute(query)

            # Broadcast message
            await manager.broadcast({"username": username, "text": text})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/messages")
async def get_messages():
    query = Message.__table__.select().order_by(Message.id.desc()).limit(50)
    messages = await db.fetch_all(query)
    return messages

# --- SHROKAI bot ---
async def fetch_news():
    TWITTER_API_BEARER_TOKEN = os.getenv("TWITTER_API_BEARER_TOKEN")
    if not TWITTER_API_BEARER_TOKEN:
        raise ValueError("Переменная окружения TWITTER_API_BEARER_TOKEN не найдена")

    url = "https://api.twitter.com/2/tweets/search/recent?query=crypto"
    headers = {"Authorization": f"Bearer {TWITTER_API_BEARER_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tweets = response.json().get("data", [])
        return [tweet["text"] for tweet in tweets]
    return []

@app.get("/bot")
async def bot():
    try:
        news = await fetch_news()
        if news:
            latest_news = news[0]
            tts = gTTS(text=latest_news, lang="en")
            tts.save("latest_news.mp3")
            return {"news": latest_news}
    except Exception as e:
        logging.error(f"Error fetching news: {e}")
        return {"error": str(e)}

    return {"news": "No news found"}
