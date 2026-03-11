from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/helpey"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/helpey"

    # JWT
    JWT_SECRET: str = "change-me-in-production-min-32-chars!"
    JWT_EXPIRY_DAYS: int = 7

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Google Gemini (embeddings)
    GEMINI_API_KEY: str = ""

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # File uploads
    UPLOADS_DIR: str = "./uploads"

    # Celery
    CELERY_BROKER_URL: str = "sqla+sqlite:///celery.db"
    CELERY_RESULT_BACKEND: str = "db+sqlite:///celery_results.db"

    # WorkOS SSO
    WORKOS_API_KEY: str = ""
    WORKOS_CLIENT_ID: str = ""
    WORKOS_ORGANIZATION_ID: str = ""
    WORKOS_REDIRECT_URI: str = "http://localhost:8000/api/auth/workos/callback"

    # Frontend URL (for CORS)
    FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()
