from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.routers.chat import router as chat_router
from app.websockets.router import router as websockets_router


app = FastAPI(proxy_headers=True)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "*.ngrok-free.app",
        "*.ngrok.io",
        "localhost",
        "127.0.0.1",
        "*.onrender.com",
    ],
)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(websockets_router)
