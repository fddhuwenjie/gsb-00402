import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CBOM Analyzer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:8081,http://localhost:5173")

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/app/uploads")
    CODE_SCAN_DIR: str = os.getenv("CODE_SCAN_DIR", "/app/scans")

    ALLOWED_SIGNATURE_EXTENSIONS: set[str] = {".yar", ".yara"}
    FUZZY_MATCH_THRESHOLD: float = 0.6
    MAX_FILE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
