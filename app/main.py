from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.services.ai_interview.router import router as interview_router
from app.services.job_description.router import router as job_fit_router
from app.services.resume_parsing.router import router as resume_router
from app.services.schedule_parsing.router import router as schedule_router

settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] if settings.cors_origins != "*" else ["*"]

from fastapi.responses import JSONResponse
from fastapi import Request

app = FastAPI(
    title="Career Services API",
    description="Resume parsing, job fit analysis, and AI interview endpoints for NUPAL (data persistence via NUPAL-Core backend APIs).",
    version="1.1.0",
)

from starlette.exceptions import HTTPException as StarletteHTTPException
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal Server Error", "message": str(exc)},
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
app.include_router(schedule_router, prefix="/v1")


@app.get("/health")
async def health() -> dict[str, str | bool]:
    core_backend_configured = bool(settings.core_backend_url.strip())
    return {
        "status": "ok" if core_backend_configured else "degraded",
        "coreBackendConfigured": core_backend_configured,
    }
