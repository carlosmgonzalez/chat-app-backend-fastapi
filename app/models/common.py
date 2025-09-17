import uuid
from pydantic import BaseModel


class UserResponse(BaseModel):  # Nueva clase para respuestas
    id: uuid.UUID
    name: str
    email: str
