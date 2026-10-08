"""One-time initialisation of database and component catalog."""

import logging
import time

from fastapi import FastAPI

from app.catalog import load_catalog, seed_components
from app.config import settings
from app.db import Base, make_engine, make_session_factory

log = logging.getLogger("robocraft")
INIT_ATTEMPTS = 3


def ensure_ready(app: FastAPI) -> None:
    """Create tables, seed the component library and load it, exactly once.

    Runs at start-up and again lazily from the request dependencies, so an instance whose
    start-up failed (a database hiccup, or two cold starts creating tables at once) recovers
    on its next request instead of failing forever.
    """
    if getattr(app.state, "session_factory", None) is not None:
        return
    with app.state.init_lock:
        if getattr(app.state, "session_factory", None) is not None:
            return
        for attempt in range(1, INIT_ATTEMPTS + 1):
            engine = make_engine(app.state.database_url, serverless=settings.serverless)
            try:
                Base.metadata.create_all(engine)
                factory = make_session_factory(engine)
                with factory() as session:
                    seed_components(session)
                    app.state.catalog = load_catalog(session)
            except Exception:
                engine.dispose()
                if attempt == INIT_ATTEMPTS:
                    raise
                log.warning("Start-up attempt %d failed, retrying", attempt, exc_info=True)
                time.sleep(0.5 * attempt)
                continue
            app.state.engine = engine
            app.state.session_factory = factory
            return
