import uuid
from pydantic import BaseModel
from app.core.env_config import env
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import func
from sqlmodel import Session, select
from .auth import get_user
from app.db.session import get_session
from app.models.chat import Chat, ChatType, ChatUser

SECRET_KEY = env.SECRET_KEY
ALGORITHM = env.ALGORITHM

router = APIRouter(prefix="/chat")

security = HTTPBearer()

class TokenData(BaseModel):
    id: str
    email: str
    name: str

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials

        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)

        user_id = payload.get("id")
        email = payload.get("email")
        name = payload.get("name")

        if user_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(
            id=user_id,
            email=email,
            name=name
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

class NewDirectChatRequest(BaseModel):
    user_email: str


@router.post("/new-direct")
def create_new_chat_direct(
    body: NewDirectChatRequest,
    current_user: TokenData = Depends(verify_token),
    session: Session = Depends(get_session),
):
    the_other_user = get_user(body.user_email, session)
    if not the_other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The other user not found"
        )

    # Check if a chat between these two users already exists
    current_user_id_as_uuid = uuid.UUID(current_user.id)
    statement = (
        select(Chat)
        .join(ChatUser)
        .where(Chat.type == ChatType.DIRECT)
        .where(getattr(ChatUser, "user_id").in_([current_user_id_as_uuid, the_other_user.id]))
        .group_by(getattr(Chat, "id"))
        .having(func.count(getattr(Chat, "id")) == 2)
    )
    existing_chat = session.exec(statement).first()

    if existing_chat:
        return existing_chat

    chat = Chat(
        name=f"Direct chat between {current_user.name} and {the_other_user.name}",
        type=ChatType.DIRECT,
    )
    session.add(chat)

    user_in_chat = ChatUser(chat_id=chat.id, user_id=uuid.UUID(current_user.id))
    session.add(user_in_chat)
    other_user_in_chat = ChatUser(chat_id=chat.id, user_id=the_other_user.id)
    session.add(other_user_in_chat)

    session.commit()

    session.refresh(chat)

    return chat
