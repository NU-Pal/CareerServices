"""MongoDB client — same cluster and DB name as NUPAL.Core (DependencyInjection GetDatabase(\"nupal\"))."""

from collections.abc import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    settings = get_settings()
    if not settings.mongo_url.strip():
        raise RuntimeError(
            "MONGO_URL is not configured. Use the same Atlas URI as NUPAL-Core-Services (MONGO_URL)."
        )
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=10_000,
        )
    return _client


def get_database() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_mongo_client()[settings.mongo_database]


def resume_collection():
    return get_database()["resume_analyses"]


def job_fit_collection():
    return get_database()["job_fit_results"]


async def close_mongo_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def mongo_lifespan() -> AsyncGenerator[None, None]:
    """Verify connectivity on startup; close client on shutdown."""
    settings = get_settings()
    if settings.mongo_url.strip():
        client = get_mongo_client()
        await client.admin.command("ping")
    yield
    await close_mongo_client()
