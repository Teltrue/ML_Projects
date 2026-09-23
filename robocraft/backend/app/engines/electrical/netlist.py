"""Circuit builder: parts, wires, pin allocation, rule-check results and the bill of materials."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from app.catalog import Catalog, Component

Severity = Literal["pass", "info", "warning", "error"]
WireKind = Literal["power", "ground", "signal", "motor"]

# Diagram columns, left to right.
COL_SOURCE, COL_POWER, COL_MCU, COL_DRIVER, COL_LOAD = range(5)


@dataclass
class Check:
    id: str
    severity: Severity
    title: str
    detail: str
    fix: str | None = None
    auto_fixed: bool = False
    engine: Literal["mechanical", "electrical"] = "electrical"


@dataclass
class Part:
    ref: str
    component: Component
    label: str
    column: int
    reason: str
    auto_added: bool = False
    in_diagram: bool = True
    note: str | None = None
    pins: list[str] = field(default_factory=list)

    def use(self, pin: str) -> None:
        if pin not in self.pins:
            self.pins.append(pin)


@dataclass
class Wire:
    a: str
    a_pin: str
    b: str
    b_pin: str
    net: str
    kind: WireKind


class PinAllocationError(RuntimeError):
    pass


class Circuit:
    def __init__(self, catalog: Catalog, board: Component):
        self.catalog = catalog
        self.board = board
        self.parts: list[Part] = []
        self.wires: list[Wire] = []
        self.checks: list[Check] = []
        self.rails: list[dict] = []
        self.pin_map: dict[str, int] = {}
        self.pin_labels: dict[str, str] = {}
        self._used: set[int] = set()
        self._counters: dict[str, int] = defaultdict(int)
        self.mcu = self.add(board.id, prefix="U", label=board.name, column=COL_MCU,
                            reason="Main controller - runs the generated firmware")

    # ----------------------------------------------------------------- parts & wires

    def add(self, component_id: str, *, prefix: str, label: str, column: int, reason: str,
            auto_added: bool = False, in_diagram: bool = True, note: str | None = None) -> Part:
        component = self.catalog.get(component_id)
        self._counters[prefix] += 1
        part = Part(f"{prefix}{self._counters[prefix]}", component, label, column, reason,
                    auto_added, in_diagram, note)
        self.parts.append(part)
        return part

    def wire(self, a: Part, a_pin: str, b: Part, b_pin: str, net: str, kind: WireKind) -> None:
        a.use(a_pin)
        b.use(b_pin)
        self.wires.append(Wire(a.ref, a_pin, b.ref, b_pin, net, kind))

    def check(self, id: str, severity: Severity, title: str, detail: str, fix: str | None = None,
              auto_fixed: bool = False, engine: Literal["mechanical", "electrical"] = "electrical"
              ) -> None:
        self.checks.append(Check(id, severity, title, detail, fix, auto_fixed, engine))

    # ----------------------------------------------------------------- MCU pins

    def pin_label(self, pin: int) -> str:
        return f"{self.board.spec('pin_prefix', '')}{pin}"

    def allocate(self, pool: str, signal: str) -> str:
        """Reserve the next free MCU pin from ``pool`` for ``signal``; returns its label."""
        pools = self.board.spec("pools", {})
        order = list(pools.get(pool, []))
        if pool == "input":  # any spare general-purpose pin can read a signal
            order += pools.get("digital", [])
        for pin in order:
            if pin not in self._used:
                self._used.add(pin)
                self.pin_map[signal] = pin
                self.pin_labels[signal] = self.pin_label(pin)
                return self.pin_labels[signal]
        raise PinAllocationError(f"{self.board.name} has no free {pool} pin for {signal}")

    # ----------------------------------------------------------------- outputs

    def bom(self) -> list[dict]:
        grouped: dict[str, dict] = {}
        for part in self.parts:
            c = part.component
            item = grouped.setdefault(c.id, {
                "component_id": c.id, "name": c.name, "category": c.category, "qty": 0,
                "unit_price_usd": c.price_usd, "refs": [], "reasons": [], "auto_added": False,
                "notes": [],
            })
            item["qty"] += 1
            item["refs"].append(part.ref)
            if part.reason not in item["reasons"]:
                item["reasons"].append(part.reason)
            if part.note and part.note not in item["notes"]:
                item["notes"].append(part.note)
            item["auto_added"] = item["auto_added"] or part.auto_added
        items = []
        for item in grouped.values():
            item["total_usd"] = round(item["qty"] * item["unit_price_usd"], 2)
            item["reason"] = "; ".join(item.pop("reasons"))
            item["note"] = "; ".join(item.pop("notes")) or None
            items.append(item)
        return items

    def total_cost(self) -> float:
        return round(sum(p.component.price_usd for p in self.parts), 2)

    def to_dict(self) -> dict:
        return {
            "board": {"id": self.board.id, "name": self.board.name,
                      "logic_v": self.board.spec("logic_v"),
                      "languages": self.board.spec("languages", [])},
            "parts": [
                {"ref": p.ref, "component_id": p.component.id, "name": p.component.name,
                 "label": p.label, "category": p.component.category, "column": p.column,
                 "pins": p.pins, "auto_added": p.auto_added, "in_diagram": p.in_diagram,
                 "reason": p.reason}
                for p in self.parts
            ],
            "wires": [w.__dict__ for w in self.wires],
            "bom": self.bom(),
            "rails": self.rails,
            "checks": [c.__dict__ for c in self.checks],
            "pin_map": self.pin_map,
            "pin_labels": self.pin_labels,
            "total_cost_usd": self.total_cost(),
        }
