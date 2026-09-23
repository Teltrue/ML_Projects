"""FastAPI dependencies."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.catalog import Catalog


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
