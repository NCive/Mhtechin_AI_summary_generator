from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import init_db
from app.services.live_stream import live_session_manager
from app.services.worker import worker_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and create tables on startup
    init_db()
    worker_manager.start()
    live_session_manager.start_recovery_tasks()
    yield
    await live_session_manager.cancel_all_recovery_tasks()
    await worker_manager.stop()


app = FastAPI(
    title="Chatmeet Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup for http://localhost:3000 and configured origins
cors_origins = (
    list(settings.CORS_ORIGINS)
    if isinstance(settings.CORS_ORIGINS, list)
    else [settings.CORS_ORIGINS]
)
for o in ("http://localhost:3000", "http://127.0.0.1:3000"):
    if o not in cors_origins:
        cors_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def root():
    return {
        "name": "Chatmeet Backend API",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "frontend": "http://localhost:3000",
    }


# Root health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}


from app.routers.meetings import router as meetings_router
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meetings_router)
app.include_router(api_router)
