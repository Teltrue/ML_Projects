"""Database engine, session factory and ORM models.

PostgreSQL is the production target (see docker-compose.yml); SQLite is used for local
development and tests. JSON columns use JSONB on PostgreSQL.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, String, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class ComponentRow(Base):
    """A standard part in the component library (motor, driver, board, battery, ...)."""

    __tablename__ = "components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    mass_kg: Mapped[float] = mapped_column(Float, default=0.0)
    specs: Mapped[dict] = mapped_column(JsonType, default=dict)


class ProjectRow(Base):
    """A user's saved design."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    template: Mapped[str] = mapped_column(String(32), index=True)
    design: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        yield session
