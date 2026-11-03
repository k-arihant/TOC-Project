from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://ps9_user:ps9_password@localhost:5432/ps9"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000/api/v1"
    API_KEY: Optional[str] = None
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"

    RANDOM_SEED: int = 0
    LOG_LEVEL: str = "INFO"
    UPLOAD_MAX_MB: int = 10
    PACKET_MAX_MB: int = 25
    PACKET_MAX_PACKETS: int = 50000

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
