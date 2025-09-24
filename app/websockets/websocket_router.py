from typing import Annotated
import uuid
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Query,
    status,
)
from sqlmodel import Session
from jwt.exceptions import InvalidTokenError

from app.db.session import get_session
from app.models.chat_model import Message
from app.routers.auth_router import get_user_from_token
from app.websockets.manager import ConnectionManager


router = APIRouter()

# Instancia del gestor de conexiones
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Query()] = None,
):
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        current_user = get_user_from_token(token)
    except (ValueError, InvalidTokenError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Convirtiendo el user_id el cual es un str a uuid.UUID
    user_id = current_user.id
    user_id_str = str(current_user.id)

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

            elif message_type == "new_chat":
                receiver_user = data.get("receiver_user")

                chat_id = data.get("chat_id")

                await manager.send_to_user(user_id=receiver_user.id, message={
                    "type": "new_chat",
                    "receiver_user": receiver_user,
                    "chat_id": chat_id
                })

            elif message_type == "unsubscribe_chat":
                await manager.unsubscribe_from_chat(user_id, chat_id)

            elif message_type == "send_message":
                message_content: dict[str, str] = data.get("content")
                print(message_content)

                # Aquí se guarda el mensaje en la base de datos
                # created_at_str = data.get("content", {}).get("created_at")
                message_data = {
                    "content": message_content["message"],
                    "chat_id": chat_id,
                    "sender_id": user_id,
                }

                message = Message(**message_data)
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
                        "sender": {
                            "id": user_id_str,
                            "name": message.sender.name,
                            "email": message.sender.email,
                        },
                        "content": {
                            "message": message_content["message"],
                            "created_at": str(message.sent_at),
                        },
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
