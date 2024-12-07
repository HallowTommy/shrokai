from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database
from gtts import gTTS
import requests

DATABASE_URL = "sqlite:///./chat.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
db = Database(DATABASE_URL)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    text = Column(Text)

Base.metadata.create_all(bind=engine)

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            username = data.get("username")
            text = data.get("text")

            query = Message.__table__.insert().values(username=username, text=text)
            await db.execute(query)

            await manager.broadcast({"username": username, "text": text})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/messages")
async def get_messages():
    query = Message.__table__.select().order_by(Message.id.desc()).limit(50)
    messages = await db.fetch_all(query)
    return messages

async def fetch_news():
    url = "https://api.twitter.com/2/tweets/search/recent?query=crypto"
    headers = {"Authorization": "Bearer YOUR_TWITTER_API_BEARER_TOKEN"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tweets = response.json().get("data", [])
        return [tweet["text"] for tweet in tweets]
    return []

@app.get("/bot")
async def bot():
    news = await fetch_news()
    if news:
        latest_news = news[0]
        tts = gTTS(text=latest_news, lang="en")
        tts.save("latest_news.mp3")
        return {"news": latest_news}
    return {"news": "No news found"}
