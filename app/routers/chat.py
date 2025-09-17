from typing import Annotated
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    status,
)
from sqlmodel import Session, select
from app.db.session import get_session
from .auth import TokenData, verify_token, get_user
from app.models.chat import Chat, ChatUser, ChatType, Message, ChatResponse
from sqlalchemy import func
from pydantic import BaseModel
import uuid


router = APIRouter(prefix="/chat")


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
        self, user_id: uuid.UUID, message: dict[str, str | list[str]]
    ):
        """Envía un mensaje a todas las conexiones de un usuario"""
        if user_id in self.user_connections:
            disconnected = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)

            for connection in disconnected:
                self.disconnect_user(user_id, connection)

    async def broadcast_to_chat(
        self,
        chat_id: uuid.UUID,
        message: dict[str, str | list[str]],
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


# Instancia global
manager = ConnectionManager()


@router.websocket("/ws/{user_id_str}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id_str: str,
    session: Annotated[Session, Depends(get_session)],
):
    # Convirtiendo el user_id el cual es un str a uuid.UUID
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        print(f"Connection rejected: Invalid user_id format '{user_id_str}'")
        return

    await manager.connect_user(user_id, websocket)

    await manager.notify_user_status(user_id, "online")

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            # Obteniendo y convirtiendo una sola vez el chat_id que es un str a uuid.UUID
            chat_id_str = data.get("chat_id")
            if not chat_id_str:
                continue

            try:
                chat_id = uuid.UUID(chat_id_str)
            except ValueError:
                print(f"Invalid UUID for chat_id: {chat_id_str}")
                continue

            if message_type == "subscribe_chat":
                await manager.subscribe_to_chat(user_id, chat_id)
                # Enviar usuarios online en el chat
                online_users = manager.get_online_users_in_chat(chat_id)
                await manager.send_to_user(
                    user_id,
                    {
                        "type": "chat_online_users",
                        "chat_id": chat_id_str,
                        "online_users": [str(u) for u in online_users],
                    },
                )

            elif message_type == "unsubscribe_chat":
                await manager.unsubscribe_from_chat(user_id, chat_id)

            elif message_type == "send_message":
                message_content = data.get("content")
                print(message_content)

                # Aquí guardarías el mensaje en la base de datos
                # message_id = await save_message_to_db(user_id, chat_id, message_content)

                message = Message(
                    content=message_content["message"],
                    chat_id=chat_id,
                    sender_id=user_id,
                )
                session.add(message)
                session.commit()
                session.refresh(message)

                # Broadcast del mensaje a otros usuarios en el chat
                await manager.broadcast_to_chat(
                    chat_id,
                    {
                        "type": "new_message",
                        "message_id": str(message.id),
                        "chat_id": chat_id_str,
                        "user_id": user_id_str,
                        "content": message_content,
                    },
                    exclude_user=user_id,
                )

            elif message_type == "typing":
                await manager.broadcast_to_chat(
                    chat_id,
                    {"type": "typing", "chat_id": chat_id_str, "user_id": user_id_str},
                    exclude_user=user_id,
                )

    except WebSocketDisconnect:
        manager.disconnect_user(user_id, websocket)
        # Notificar que el usuario está offline
        await manager.notify_user_status(user_id, "offline")


class NewDirectChatRequest(BaseModel):
    receiver_user_email: str


@router.post("/new")
def create_new_chat(
    body: NewDirectChatRequest,
    current_user: Annotated[TokenData, Depends(verify_token)],
    session: Annotated[Session, Depends(get_session)],
):
    receiver_user = get_user(body.receiver_user_email, session)
    if not receiver_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The other user not found"
        )

    # Check if a chat between these two users already exists
    statement = (
        select(Chat)
        .join(ChatUser)
        .where(Chat.type == ChatType.DIRECT)
        .where(getattr(ChatUser, "user_id").in_([current_user.id, receiver_user.id]))
        .group_by(getattr(Chat, "id"))
        .having(func.count(getattr(Chat, "id")) == 2)
    )
    existing_chat = session.exec(statement).first()

    if existing_chat:
        return existing_chat

    chat = Chat(
        name=f"Direct chat between {current_user.name} and {receiver_user.name}",
        type=ChatType.DIRECT,
    )
    session.add(chat)

    current_user_in_chat = ChatUser(chat_id=chat.id, user_id=current_user.id)
    session.add(current_user_in_chat)
    receiver_user_in_chat = ChatUser(chat_id=chat.id, user_id=receiver_user.id)
    session.add(receiver_user_in_chat)

    session.commit()

    session.refresh(chat)

    return chat


@router.get("/{chat_id}", response_model=ChatResponse)
def get_chat_by_id(
    chat_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]
):
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Chat with id {str(chat_id)} not found"
        )
    return chat
