import uuid
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Conexiones activas por usuario: dict[user_id, list[websocket]]
        self.user_connections: dict[uuid.UUID, list[WebSocket]] = {}
        # Mapeo de que chats esta "escuchando" cada usuario: dict[user_id, set[chat_id]]
        self.user_chat_subscriptions: dict[uuid.UUID, set[uuid.UUID]] = {}
        # Mapeo inverso: que usuario estan en cada chat: dict[chat_id, set[user_id]]
        self.chat_participants: dict[uuid.UUID, set[uuid.UUID]] = {}

    async def connect_user(self, user_id: uuid.UUID, websocket: WebSocket):
        """Conecta un usuario y acepta el WebSocket"""
        await websocket.accept()

        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)

        if user_id not in self.user_chat_subscriptions:
            self.user_chat_subscriptions[user_id] = set()

    def disconnect_user(self, user_id: uuid.UUID, websocket: WebSocket):
        """Desconecta un usuario especifico"""
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)

            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

                if user_id in self.user_chat_subscriptions:
                    for chat_id in self.user_chat_subscriptions[user_id]:
                        if chat_id in self.chat_participants:
                            self.chat_participants[chat_id].discard(user_id)
                    del self.user_chat_subscriptions[user_id]

    async def subscribe_to_chat(self, user_id: uuid.UUID, chat_id: uuid.UUID):
        """Suscribe a un usuario a un chat especifico"""
        if user_id not in self.user_chat_subscriptions:
            self.user_chat_subscriptions[user_id] = set()
        self.user_chat_subscriptions[user_id].add(chat_id)

        if chat_id not in self.chat_participants:
            self.chat_participants[chat_id] = set()
        self.chat_participants[chat_id].add(user_id)

    async def unsubscribe_from_chat(self, user_id: uuid.UUID, chat_id: uuid.UUID):
        """Desuscribe a un usuario a un chat"""
        if user_id in self.user_chat_subscriptions:
            self.user_chat_subscriptions[user_id].discard(chat_id)

        if chat_id in self.chat_participants:
            self.chat_participants[chat_id].discard(user_id)

    async def send_to_user(
        self, user_id: uuid.UUID, message: dict[str, str | list[str] | dict[str, str]]
    ):
        """Envía un mensaje a todas las conexiones de un usuario"""
        if user_id in self.user_connections:
            disconnected = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)

            for connection in disconnected:
                self.disconnect_user(user_id, connection)

    async def broadcast_to_chat(
        self,
        chat_id: uuid.UUID,
        message: dict[str, str | list[str] | dict[str, str]],
        exclude_user: uuid.UUID | None = None,
    ):
        """Envía un mensaje a todos los usuarios suscritos a un chat"""
        if chat_id in self.chat_participants:
            for user_id in self.chat_participants[chat_id]:
                if exclude_user is None or user_id != exclude_user:
                    await self.send_to_user(user_id, message)

    async def notify_user_status(self, user_id: uuid.UUID, status: str):
        """Notifica cambios de estado de usuario a sus chats activos"""
        if user_id in self.user_chat_subscriptions:
            for chat_id in self.user_chat_subscriptions[user_id]:
                await self.broadcast_to_chat(
                    chat_id,
                    {
                        "type": "user_status",
                        "user_id": str(user_id),
                        "status": status,
                        "chat_id": str(chat_id),
                    },
                    exclude_user=user_id,
                )

    def get_online_users_in_chat(self, chat_id: uuid.UUID) -> list[uuid.UUID]:
        """Obtiene lista de usuarios online en un chat"""
        if chat_id not in self.chat_participants:
            return []

        online_users = []
        for user_id in self.chat_participants[chat_id]:
            if user_id in self.user_connections:
                online_users.append(user_id)

        return online_users
