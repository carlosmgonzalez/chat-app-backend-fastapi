from typing import Annotated
from fastapi import Depends
from sqlmodel import create_engine, SQLModel, Session
from app.core.env_config import env
from app import models

engine = create_engine(str(env.DATABASE_URL), echo=True)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]
