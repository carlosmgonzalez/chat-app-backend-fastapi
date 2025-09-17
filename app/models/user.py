from datetime import datetime
import uuid
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING
from .chat import ChatUser

if TYPE_CHECKING:
    from .chat import Chat, Message


class UserBase(SQLModel):
    name: str
    email: str = Field(unique=True, index=True)
    hashed_password: str


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)

    # Relationships
    chats: list["Chat"] = Relationship(back_populates="users", link_model=ChatUser)
    messages: list["Message"] = Relationship(back_populates="sender")


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
