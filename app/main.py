from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.mongo_db import close_mongo_client, get_mongo_client
from app.services.ai_interview.router import router as interview_router
from app.services.job_description.router import router as job_fit_router
from app.services.resume_parsing.router import router as resume_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.mongo_url.strip():
        await get_mongo_client().admin.command("ping")
    yield
    await close_mongo_client()


settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] if settings.cors_origins != "*" else ["*"]

app = FastAPI(
    title="Career Services API",
    description="Resume parsing, job fit analysis, and AI interview endpoints for NUPAL (MongoDB shared with NUPAL.Core).",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router, prefix="/v1")
app.include_router(job_fit_router, prefix="/v1")
app.include_router(interview_router, prefix="/v1")


@app.get("/health")
async def health() -> dict[str, str | bool]:
    settings = get_settings()
    mongo_ok = not settings.mongo_url.strip()
    if settings.mongo_url.strip():
        try:
            await get_mongo_client().admin.command("ping")
            mongo_ok = True
        except Exception:
            mongo_ok = False
    return {"status": "ok" if mongo_ok else "degraded", "mongo": mongo_ok}
