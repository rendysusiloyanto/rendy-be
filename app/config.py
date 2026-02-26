from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./app.db"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8001/api/auth/google/callback"

    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Frontend URL for CORS
    frontend_url: str = "http://localhost:3000"

    # Support/QRIS: path absolut ke folder upload (kosong = pakai relative ke backend)
    support_upload_dir: str = ""

    # Premium request: path folder upload bukti transfer (kosong = backend/uploads/premium)
    premium_upload_dir: str = ""

    # Video upload: path folder for streamed videos (kosong = backend/uploads/videos)
    video_upload_dir: str = ""

    # Video stream token expiry (minutes)
    video_stream_token_expire_minutes: int = 60

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
