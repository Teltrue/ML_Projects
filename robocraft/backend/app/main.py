"""RoboCraft API entry point: ``uvicorn app.main:app --reload``."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.catalog import load_catalog, seed_components
from app.config import settings
from app.db import Base, make_engine, make_session_factory
from app.engines.codegen.generator import CodegenError
from app.pipeline import DesignError
from app.routers import catalog, engines, projects


def create_app(database_url: str | None = None) -> FastAPI:
    url = database_url or settings.database_url

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(url)
        Base.metadata.create_all(engine)
        factory = make_session_factory(engine)
        with factory() as session:
            seed_components(session)
            app.state.catalog = load_catalog(session)
        app.state.session_factory = factory
        yield
        engine.dispose()

    app = FastAPI(
        title="RoboCraft API",
        version="0.1.0",
        description="Mechanical, electrical and code-generation engines for beginner robotics.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DesignError)
    @app.exception_handler(CodegenError)
    async def _unprocessable(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(catalog.router)
    app.include_router(engines.router)
    app.include_router(projects.router)
    return app


app = create_app()
