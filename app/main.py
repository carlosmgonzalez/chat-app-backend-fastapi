from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.routers.chat import router as chat_router


app = FastAPI()

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
