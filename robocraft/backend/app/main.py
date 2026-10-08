"""RoboCraft API entry point: ``uvicorn app.main:app --reload``.

Vercel auto-detects this module (``app/main.py``) and serves ``app`` as a FastAPI function.
"""

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.engines.codegen.generator import CodegenError
from app.pipeline import DesignError
from app.routers import catalog, engines, projects
from app.startup import ensure_ready

log = logging.getLogger("robocraft")


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            ensure_ready(app)
        except Exception:
            log.exception("Start-up failed; will retry on the first request")
        yield
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="RoboCraft API",
        version="0.1.0",
        description="Mechanical, electrical and code-generation engines for beginner robotics.",
        lifespan=lifespan,
    )
    app.state.database_url = database_url or settings.database_url
    app.state.init_lock = threading.Lock()
    app.state.session_factory = None
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
