from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""       # Used by: resume parsing, job fit analysis
    groq_api_key_2: str = ""     # Used by: AI interview (generate questions + feedback)
    deepgram_api_key: str = ""
    career_services_api_key: str = ""
    core_backend_url: str = ""
    core_backend_api_key: str = ""
    cors_origins: str = "*"
    groq_model: str = "llama-3.3-70b-versatile"


@lru_cache
def get_settings() -> Settings:
    return Settings()
