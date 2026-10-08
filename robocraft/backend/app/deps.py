"""FastAPI dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.catalog import Catalog
from app.startup import ensure_ready


def get_catalog(request: Request) -> Catalog:
    ensure_ready(request.app)
    return request.app.state.catalog


def get_db(request: Request) -> Iterator[Session]:
    ensure_ready(request.app)
    with request.app.state.session_factory() as session:
        yield session
