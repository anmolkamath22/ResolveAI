"""Central runtime configuration; secrets are environment-only."""
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv("RESOLVEAI_DATABASE_PATH", "resolveai.db")
    api_key: str | None = os.getenv("RESOLVEAI_API_KEY")
    cors_origin: str = os.getenv("RESOLVEAI_CORS_ORIGIN", "http://localhost:8501,http://localhost:5173")

settings=Settings()
