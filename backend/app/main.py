from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and create tables on startup
    init_db()
    yield


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
if "http://localhost:3000" not in cors_origins:
    cors_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}


from app.routers.meetings import router as meetings_router
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meetings_router)
app.include_router(api_router)
