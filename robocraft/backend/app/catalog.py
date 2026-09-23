"""The component library.

Components live in the database (``components`` table). They are seeded/upserted from
``data/components.json`` at start-up and loaded into an immutable in-memory :class:`Catalog`
that the engines consume, so the engines themselves stay pure and easy to test.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ComponentRow

DATA_FILE = Path(__file__).parent / "data" / "components.json"


class CatalogError(KeyError):
    pass


@dataclass(frozen=True)
class Component:
    id: str
    category: str
    name: str
    description: str = ""
    price_usd: float = 0.0
    mass_kg: float = 0.0
    specs: dict[str, Any] = field(default_factory=dict)

    def spec(self, key: str, default: Any = None) -> Any:
        return self.specs.get(key, default)


class Catalog:
    def __init__(self, components: Iterable[Component]):
        self._by_id = {c.id: c for c in components}

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, component_id: str) -> bool:
        return component_id in self._by_id

    def get(self, component_id: str) -> Component:
        try:
            return self._by_id[component_id]
        except KeyError as exc:
            raise CatalogError(f"Unknown component '{component_id}'") from exc

    def by_category(self, category: str) -> list[Component]:
        return [c for c in self._by_id.values() if c.category == category]

    def all(self) -> list[Component]:
        return list(self._by_id.values())


def _read_seed() -> list[dict[str, Any]]:
    return json.loads(DATA_FILE.read_text())["components"]


@lru_cache(maxsize=1)
def default_catalog() -> Catalog:
    """Catalog built straight from the seed file (used by tests and as a DB fallback)."""
    return Catalog(Component(**item) for item in _read_seed())


def seed_components(session: Session) -> int:
    """Insert or update every component from the seed file. Returns the number written."""
    items = _read_seed()
    for item in items:
        session.merge(ComponentRow(**item))
    session.commit()
    return len(items)


def load_catalog(session: Session) -> Catalog:
    rows = session.scalars(select(ComponentRow)).all()
    return Catalog(
        Component(
            id=r.id,
            category=r.category,
            name=r.name,
            description=r.description,
            price_usd=r.price_usd,
            mass_kg=r.mass_kg,
            specs=dict(r.specs or {}),
        )
        for r in rows
    )
