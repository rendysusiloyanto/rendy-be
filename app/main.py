import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, users, request_access, openvpn, ukk, learning, announcements, support, premium
from app.openvpn.background import openvpn_traffic_poller

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = {"traffic_snapshot": {}, "traffic_ws_clients": []}
    app.state.openvpn_traffic = state
    task = asyncio.create_task(openvpn_traffic_poller(state))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Auth API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "https://ukk.jns23.cloud"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(request_access.router)
app.include_router(users.router)
app.include_router(openvpn.router)
app.include_router(ukk.router)
app.include_router(learning.router)
app.include_router(announcements.router)
app.include_router(support.router)
app.include_router(premium.router)


@app.get("/")
def root():
    return {"message": "Auth API", "docs": "/docs"}
