from typing import Annotated
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlmodel import Session, select
from app.db.session import get_session
from .auth import TokenData, verify_token, get_user
from app.models.chat import (
    Chat,
    ChatUser,
    ChatType,
    ChatResponse,
    UserChatsResponse,
)
from sqlalchemy import func
from sqlalchemy.orm import noload, selectinload
from pydantic import BaseModel
import uuid


router = APIRouter(prefix="/chat")


class NewDirectChatRequest(BaseModel):
    receiver_user_email: str


@router.get("/", response_model=list[UserChatsResponse])
def get_user_chats(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[TokenData, Depends(verify_token)],
):
    """Get all chats for a given user"""

    statement = (
        select(Chat)
        .join(ChatUser)
        .where(ChatUser.user_id == current_user.id)
        .options(
            selectinload(getattr(Chat, "users")), noload(getattr(Chat, "messages"))
        )
    )

    user_chats = session.exec(statement).all()

    if not user_chats:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found any chat")

    return user_chats


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
    chat_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[TokenData, Depends(verify_token)],
):
    statement = (
        select(Chat)
        .join(ChatUser)
        .where(Chat.id == chat_id)
        .where(ChatUser.user_id == current_user.id)
    )

    chat = session.exec(statement).first()

    if not chat:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Chat with id {str(chat_id)} not found"
        )
    return chat
