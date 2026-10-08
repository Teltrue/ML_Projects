"""Runtime configuration, read from environment variables."""

import os
from dataclasses import dataclass, field


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def is_serverless() -> bool:
    """True on Vercel, which sets ``VERCEL=1`` in its functions."""
    return bool(os.getenv("VERCEL"))


def resolve_database_url() -> str:
    # Vercel's Postgres integrations (Neon, Supabase, ...) set DATABASE_URL or POSTGRES_URL.
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if url:
        # Hosted providers hand out postgres:// URLs; SQLAlchemy needs the driver spelled out.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url
    if is_serverless():
        # Serverless file systems are read-only apart from /tmp, which is per-instance and
        # wiped on cold starts: the engines still work, but saved projects need Postgres.
        return "sqlite:////tmp/robocraft.db"
    # SQLite keeps local development dependency-free; docker-compose uses PostgreSQL.
    return "sqlite:///./robocraft.db"


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=resolve_database_url)
    serverless: bool = field(default_factory=is_serverless)
    cors_origins: list[str] = field(
        default_factory=lambda: _split(
            os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        )
    )


settings = Settings()
