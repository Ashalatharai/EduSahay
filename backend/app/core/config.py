from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"
    database_url: str = "sqlite:///./edusahaya.db"
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 60
    admin_email: str | None = None
    admin_password: str | None = None
    encryption_key: str | None = None
    storage_dir: str = "../storage"
    max_upload_mb: int = 10
    classifier_path: str = str(Path(__file__).resolve().parents[2] / "models" / "doc_classifier.pt")
    classifier_min_confidence: float = 0.6
    ocr_enabled: bool = True
    extractor_dir: str = str(Path(__file__).resolve().parents[2] / "models" / "layoutlmv3")
    extraction_min_confidence: float = 0.7
    ocr_lang: str = "en"


settings = Settings()

if settings.app_env == "production" and settings.secret_key == "dev-only-change-me":
    raise RuntimeError("Set SECRET_KEY before running in production")
if settings.app_env == "production" and not settings.encryption_key:
    raise RuntimeError("Set ENCRYPTION_KEY before running in production")
