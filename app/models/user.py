from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field

class UserBase(SQLModel):
    name: str
    email: str = Field(unique=True, index=True)
    hashed_password: str

class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
