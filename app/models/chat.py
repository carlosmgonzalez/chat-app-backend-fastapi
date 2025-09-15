import enum
import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

class ChatType(str, enum.Enum):
    GROUP = "group"
    DIRECT = "direct"

class ChatUser(SQLModel, table=True):
    chat_id: uuid.UUID = Field(default=None, foreign_key="chat.id", primary_key=True)
    user_id: uuid.UUID = Field(default=None, foreign_key="user.id", primary_key=True)

class Message(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    content: str
    sent_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    chat_id: uuid.UUID = Field(default=None, foreign_key="chat.id")
    chat: "Chat" = Relationship(back_populates="messages")

    sender_id: uuid.UUID = Field(default=None, foreign_key="user.id")
    sender: "User" = Relationship(back_populates="messages")

class Chat(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: ChatType = ChatType.DIRECT
    name: str
    created_at: datetime = Field(default_factory=datetime.now)

     # Relationships
    users: List["User"] = Relationship(back_populates="chats", link_model=ChatUser)
    messages: List["Message"] = Relationship(back_populates="chat")
