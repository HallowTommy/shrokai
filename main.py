from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
import re
import time
from starlette.websockets import WebSocket as StarletteWebSocket, WebSocketDisconnect as StarletteWebSocketDisconnect
from starlette.websockets import WebSocketState

app = FastAPI()

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

current_track_index = 0
start_time = time.time()

# Бан-лист и регулярное выражение для ссылок
banned_words = ["spam", "offensive", "bannedword", "farm", "rug", "scum"]
banned_links_pattern = r"http[s]?://\S+"

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

music_manager = ConnectionManager()
chat_manager = ConnectionManager()

# Музыка
async def broadcast_music_state():
    global current_track_index, start_time
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time >= 180:
            current_track_index = (current_track_index + 1) % len(playlist)
            start_time = time.time()
            elapsed_time = 0
        state = {
            "type": "music",
            "track": current_track_index,
            "time": elapsed_time,
            "url": playlist[current_track_index]
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
    ai_socket = None

    try:
        # Подключаемся к ИИ
        ai_socket = WebSocketClient(url="ws://shrokgpt-production.up.railway.app/ws/ai")
        await ai_socket.connect()

        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            username = data.get("username", "Anonymous")

            # Фильтрация сообщений
            if any(word in message.lower() for word in banned_words):
                logger.warning(f"Message contains banned word: {message}")
                continue
            if re.search(banned_links_pattern, message):
                logger.warning(f"Message contains a link: {message}")
                continue

            # Проверяем, направлено ли сообщение ИИ
            if "@shrokai" in message.lower():
                # Отправляем сообщение ИИ
                await ai_socket.send_text(message)
                ai_response = await ai_socket.receive_text()

                # Формируем ответ ИИ
                ai_message = {
                    "type": "chat",
                    "username": "ShrokAI",
                    "message": ai_response,
                }
                await chat_manager.broadcast(ai_message)

            # Отправляем сообщение в чат
            chat_message = {
                "type": "chat",
                "username": username,
                "message": message,
            }
            await chat_manager.broadcast(chat_message)
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Chat error: {e}")
    finally:
        if ai_socket and ai_socket.state == WebSocketState.CONNECTED:
            await ai_socket.close()

@app.post("/update-banned-words/")
async def update_banned_words(words: list[str]):
    global banned_words
    banned_words = words
    return {"message": "Banned words updated.", "banned_words": banned_words}

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_music_state())
