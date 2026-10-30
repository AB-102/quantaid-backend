import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from config import APP_VERSION, CORS_ORIGINS, LOG_LEVEL, RENDER_GIT_COMMIT
from database.db import client, db
from database.seeding import seed_if_empty
from routers import admin_users, ai, auth, content, feedback, files, progress, users
from services import ai_usage_service

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# PyMongo logs every command at DEBUG level; keep it readable when ENVIRONMENT=development
logging.getLogger("pymongo").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await seed_if_empty(db)
        await ai_usage_service.create_indexes(db)
    except PyMongoError:
        logger.exception("Startup database setup failed — database may be unavailable at startup")
    yield
    await client.close()


app = FastAPI(title="Quantaid API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_headers=["Content-Type", "X-Requested-With"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(progress.router)
app.include_router(files.router)
app.include_router(content.router)
app.include_router(content.admin_router)
app.include_router(feedback.router)
app.include_router(feedback.admin_router)
app.include_router(admin_users.router)
app.include_router(ai.router)


@app.get("/health")
@app.get("/api/health")
async def health():
    """App + MongoDB check. Render, CI and Prometheus probe /health on the backend port. /api/health is the same
    check through the site's proxy: self-host health gates and outside-in probes use it.
    CI's staging deploy jobs poll it until it reports their commit; self-hosted hosts report their release."""
    try:
        await client.admin.command("ping")
        database = "connected"
    except PyMongoError:
        logger.exception("MongoDB health check failed")
        database = "error"
    return {"status": "ok", "database": database, "commit": RENDER_GIT_COMMIT, "version": APP_VERSION}
