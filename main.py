from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging

# Создаем приложение FastAPI
app = FastAPI()

# Настраиваем CORS (для Webflow или других фронтенд-приложений)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Лучше указать конкретные домены для повышения безопасности
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Класс для управления подключениями
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []  # Храним активные подключения

    async def connect(self, websocket: WebSocket):
        """Подключаем WebSocket клиента."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New connection established. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Отключаем WebSocket клиента."""
        self.active_connections.remove(websocket)
        logger.info(f"Connection closed. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Рассылаем сообщение всем подключенным клиентам."""
        logger.info(f"Broadcasting message: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket-эндпоинт для чата."""
    await manager.connect(websocket)
    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_text()
            logger.info(f"Received message: {data}")
            # Рассылаем сообщение всем подключенным клиентам
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error: {e}")
