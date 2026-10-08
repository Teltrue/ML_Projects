"""Behaviour that matters when the API runs as a serverless function (Vercel)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.catalog import seed_components
from app.config import resolve_database_url
from app.db import Base, ComponentRow, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture()
def clean_env(monkeypatch):
    for name in ("DATABASE_URL", "POSTGRES_URL", "VERCEL"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("given,expected", [
    ("postgres://u:p@db.example.com/rc?sslmode=require",
     "postgresql+psycopg://u:p@db.example.com/rc?sslmode=require"),
    ("postgresql://u:p@db.example.com/rc", "postgresql+psycopg://u:p@db.example.com/rc"),
    ("postgresql+psycopg://u:p@h/rc", "postgresql+psycopg://u:p@h/rc"),
    ("sqlite:///./other.db", "sqlite:///./other.db"),
])
def test_hosted_postgres_urls_get_the_psycopg_driver(clean_env, given, expected):
    clean_env.setenv("DATABASE_URL", given)
    assert resolve_database_url() == expected


def test_postgres_url_from_vercel_integrations_is_used(clean_env):
    clean_env.setenv("POSTGRES_URL", "postgres://u:p@h/rc")
    assert resolve_database_url() == "postgresql+psycopg://u:p@h/rc"


def test_serverless_without_database_falls_back_to_tmp(clean_env):
    assert resolve_database_url() == "sqlite:///./robocraft.db"
    clean_env.setenv("VERCEL", "1")
    assert resolve_database_url() == "sqlite:////tmp/robocraft.db"


def test_requests_work_even_if_lifespan_never_ran(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'lazy.db'}")
    client = TestClient(app)  # not used as a context manager: no lifespan events
    assert app.state.session_factory is None
    assert client.post("/api/analyze", json={"design": {"template": "rover"}}).status_code == 200
    assert client.get("/api/projects").json() == []
    assert app.state.session_factory is not None


def test_failed_start_up_recovers_on_a_later_request(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'missing-dir' / 'x.db'}")
    with TestClient(app) as client:  # start-up fails: the directory doesn't exist yet
        assert app.state.session_factory is None
        (tmp_path / "missing-dir").mkdir()
        assert client.get("/api/templates").status_code == 200


def test_seeding_only_writes_changes(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'seed.db'}", serverless=True)
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        first = seed_components(session)
        assert first > 30
        assert seed_components(session) == 0
        row = session.scalars(select(ComponentRow).where(ComponentRow.id == "sg90")).one()
        row.price_usd = 999.0
        session.commit()
        assert seed_components(session) == 1
        session.refresh(row)
        assert row.price_usd == 2.5
