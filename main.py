from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import logging
import time

# Создаем приложение FastAPI
app = FastAPI()

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Укажите конкретные домены для безопасности
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Плейлист (пути обновлены для доступа через "/media")
playlist = [
    "/media/01.%20Ma%20Holo.mp3",
    "/media/02.%20Beat%20Cop.mp3",
    "/media/03.%20The%20Stakeout%20%28feat.%20W.%20Giacchi%29.mp3",
    "/media/04.%20Conga%20Mind.mp3",
    "/media/05.%20Deep%20Cover.mp3",
    "/media/06.%20High%20Slide.mp3",
    "/media/07.%20The%20Stakeout_%20Reprise%20%28feat.%20W.%20Giacchi%29.mp3",
    "/media/08.%20Dimension%20Alley.mp3",
    "/media/09.%20Holodeck%20Blues.mp3"
]

# Текущее состояние воспроизведения
current_track_index = 0
start_time = time.time()

# Менеджеры WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New connection established. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Connection closed. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

# Создаем два менеджера для музыки и чата
music_manager = ConnectionManager()
chat_manager = ConnectionManager()

# Музыка
async def broadcast_music_state():
    global current_track_index, start_time
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time >= 180:  # Длительность трека (180 секунд)
            current_track_index = (current_track_index + 1) % len(playlist)
            start_time = time.time()
            elapsed_time = 0
        state = {
            "type": "music",
            "track": current_track_index,
            "time": elapsed_time,
            "url": playlist[current_track_index]  # Отправляем относительный путь
        }
        await music_manager.broadcast(state)
        await asyncio.sleep(1)

@app.websocket("/ws/music")
async def music_websocket_endpoint(websocket: WebSocket):
    await music_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        music_manager.disconnect(websocket)

@app.websocket("/ws/chat")
async def chat_websocket_endpoint(websocket: WebSocket):
    await chat_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat":
                chat_message = {
                    "type": "chat",
                    "username": data.get("username", "Anonymous"),
                    "message": data.get("message", "")
                }
                await chat_manager.broadcast(chat_message)
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Chat error: {e}")

# Подключение статических файлов
app.mount("/media", StaticFiles(directory="/app/media"), name="media")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_music_state())
