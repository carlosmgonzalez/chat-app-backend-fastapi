from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.routers.auth_router import router as auth_router
from app.routers.user_router import router as user_router
from app.routers.chat_router import router as chat_router
from app.websockets.websocket_router import router as websockets_router


app = FastAPI(proxy_headers=True)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "*.ngrok-free.app",
        "*.ngrok.io",
        "localhost",
        "127.0.0.1",
        "*.onrender.com",
        "*.railway.app",
    ],
)


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(websockets_router)


@app.get("/hello")
def hello():
    return "Hello world"
