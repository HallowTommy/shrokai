from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
import time

# Создаем приложение FastAPI
app = FastAPI()

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Укажите конкретный домен для безопасности
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Плейлист
playlist = [
    "https://od.lk/s/NjBfMTYxNzI3OTY3Xw/01.%20Ma%20Holo.mp3",
    "https://od.lk/s/NjBfMTYxNzI4MjQ2Xw/02.%20Beat%20Cop.mp3",
    "https://od.lk/s/NjBfMTYxNzI4MzYyXw/03.%20The%20Stakeout%20%28feat.%20W.%20Giacchi%29.mp3",
    "https://od.lk/s/NjBfMTYxNzI4NTU3Xw/04.%20Conga%20Mind.mp3",
    "https://od.lk/s/NjBfMTYxNzI4NzcwXw/05.%20Deep%20Cover.mp3",
    "https://od.lk/s/NjBfMTYxNzI4OTUwXw/06.%20High%20Slide.mp3",
    "https://od.lk/s/NjBfMTYxNzI5MTE4Xw/07.%20The%20Stakeout_%20Reprise%20%28feat.%20W.%20Giacchi%29.mp3",
    "https://od.lk/s/NjBfMTYxNzI5Mjk5Xw/08.%20Dimension%20Alley.mp3",
    "https://od.lk/s/NjBfMTYxNzI5ODAwXw/09.%20Holodeck%20Blues.mp3"
]

current_track_index = 0  # Номер текущего трека
start_time = time.time()  # Время старта воспроизведения трека

# Класс для управления подключениями
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

manager = ConnectionManager()

# Функция для рассылки состояния
async def broadcast_state():
    global current_track_index, start_time
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time >= 180:  # Пример длительности трека (180 секунд)
            current_track_index = (current_track_index + 1) % len(playlist)
            start_time = time.time()
            elapsed_time = 0
        state = {
            "track": current_track_index,
            "time": elapsed_time,
            "url": playlist[current_track_index]
        }
        await manager.broadcast(state)
        await asyncio.sleep(1)  # Рассылка каждые 1 секунду

# WebSocket эндпоинт
@app.websocket("/ws/music")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Ожидаем данные, если нужно
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Запускаем рассылку состояния
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_state())
