import os
from typing import List
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "CloudSentinel AI API"
    app_version: str = "0.1.0"
    debug: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")
    host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    port: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # Safe CORS configuration allowing local React development origins
    allowed_origins: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
