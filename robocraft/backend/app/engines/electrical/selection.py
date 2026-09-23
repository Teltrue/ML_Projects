"""Actuator, driver, battery and regulator selection from the component library."""

from dataclasses import dataclass, field

import numpy as np

from app.catalog import Catalog, Component
from app.engines.mechanical import rover as rover_mech
from app.schemas.design import RoverDesign

KGCM_TO_NM = 0.0980665
LOGIC_CURRENT_A = 0.3  # board + sensor allowance when budgeting a battery

# Utilisation (required / available torque, safety factor already included) thresholds.
OK_UTILISATION = 0.9


def to_kgcm(nm: float) -> float:
    return nm / KGCM_TO_NM


def utilisation_status(util: float) -> str:
    if util <= OK_UTILISATION:
        return "ok"
    if util <= 1.0:
        return "marginal"
    return "insufficient"


# --------------------------------------------------------------------------- servos


def servo_torque_kgcm(servo: Component, volts: float) -> float:
    """Stall torque at ``volts``: linear between datasheet points, proportional below the
    first point and capped at the last one (never extrapolate optimistically)."""
    points = sorted(servo.spec("torque_points"))
    v0, t0 = points[0]
    if volts <= v0:
        return t0 * volts / v0
    for (va, ta), (vb, tb) in zip(points, points[1:], strict=False):
        if volts <= vb:
            return ta + (tb - ta) * (volts - va) / (vb - va)
    return points[-1][1]


@dataclass
class Selection:
    role: str
    label: str
    component: Component
    required_nm: float
    available_nm: float
    rationale: str
    alternatives: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def utilisation(self) -> float:
        return self.required_nm / self.available_nm if self.available_nm > 0 else float("inf")

    @property
    def status(self) -> str:
        return utilisation_status(self.utilisation)

    def to_dict(self) -> dict:
        c = self.component
        return {
            "role": self.role, "label": self.label, "component_id": c.id, "name": c.name,
            "required_nm": self.required_nm, "required_kgcm": to_kgcm(self.required_nm),
            "available_nm": self.available_nm, "available_kgcm": to_kgcm(self.available_nm),
            "utilization": self.utilisation, "status": self.status, "rationale": self.rationale,
            "alternatives": self.alternatives, "mass_kg": c.mass_kg, "price_usd": c.price_usd,
            "extra": self.extra,
        }


def servo_candidates(catalog: Catalog, rail_v: float) -> list[Component]:
    return [s for s in catalog.by_category("servo")
            if s.spec("v_min") - 1e-9 <= rail_v <= s.spec("v_max") + 1e-9]


def select_servo(role: str, label: str, required_nm: float, rail_v: float,
                 catalog: Catalog) -> Selection:
    candidates = servo_candidates(catalog, rail_v) or catalog.by_category("servo")
    rated = sorted(((s, servo_torque_kgcm(s, rail_v) * KGCM_TO_NM) for s in candidates),
                   key=lambda item: (item[0].price_usd, item[0].mass_kg))
    # Prefer a comfortable margin; accept a marginal fit only when nothing else is strong enough.
    comfortable = [(s, t) for s, t in rated if required_nm <= OK_UTILISATION * t]
    adequate = comfortable or [(s, t) for s, t in rated if t >= required_nm]
    if adequate:
        chosen, available = adequate[0]
        rationale = (f"Cheapest servo in the library with enough torque at {rail_v:.1f} V: "
                     f"{to_kgcm(available):.1f} kg·cm available vs {to_kgcm(required_nm):.2f} "
                     f"kg·cm required.")
        others = adequate[1:3]
    else:
        chosen, available = max(rated, key=lambda item: item[1])
        rationale = (f"No servo in the library delivers {to_kgcm(required_nm):.1f} kg·cm at "
                     f"{rail_v:.1f} V; showing the strongest available.")
        others = []
    return Selection(
        role=role, label=label, component=chosen, required_nm=required_nm,
        available_nm=available, rationale=rationale,
        alternatives=[{"component_id": s.id, "name": s.name, "price_usd": s.price_usd,
                       "rating": f"{to_kgcm(t):.1f} kg·cm"} for s, t in others],
        extra={"rail_v": rail_v, "stall_current_a": chosen.spec("stall_current_a")},
    )


# --------------------------------------------------------------------------- regulators


def select_regulator(catalog: Catalog, source: Component, v_out: float,
                     current_a: float) -> Component | None:
    """Smallest buck converter that accepts the source's whole voltage range, keeps
    ``v_out`` at nominal source voltage and can supply ``current_a``."""
    v_in_min, v_in_max, v_in_nom = (source.spec("v_min"), source.spec("v_max"),
                                    source.spec("v_nom"))
    fitting = [
        r for r in catalog.by_category("regulator")
        if r.spec("v_in_min") <= v_in_min and v_in_max <= r.spec("v_in_max")
        and v_in_nom - r.spec("dropout_v") >= v_out and r.spec("continuous_a") >= current_a
    ]
    return min(fitting, key=lambda r: (r.spec("continuous_a"), r.price_usd), default=None)


def fuse_rating(catalog: Catalog, current_a: float) -> float:
    ratings = catalog.get("fuse-inline").spec("ratings_a")
    target = current_a * 1.25
    return next((r for r in ratings if r >= target), ratings[-1])


# --------------------------------------------------------------------------- rover drivetrain


@dataclass
class DriveOption:
    motor: Component
    driver: Component
    battery: Component
    loads: rover_mech.RoverLoads
    v_eff: float  # motor terminal voltage at nominal battery voltage
    v_eff_max: float  # ... on a fully charged battery
    no_load_rpm: float
    stall_nm: float
    available_nm: float  # torque the motor can deliver at the required wheel speed
    run_current_a: float  # per motor, worst-case load without safety factor
    cruise_current_a: float  # per motor, flat ground at top speed
    stall_current_a: float  # per motor at v_eff
    n_motors: int = 2
    issues: list[str] = field(default_factory=list)  # hard failures
    score: float = 0.0

    @property
    def feasible(self) -> bool:
        return not self.issues

    @property
    def motors_per_channel(self) -> int:
        return self.n_motors // 2

    @property
    def utilisation(self) -> float:
        required = self.loads.torque_per_motor_nm
        return required / self.available_nm if self.available_nm > 0 else float("inf")


def _motor_curve(motor: Component, volts: float) -> tuple[float, float, float, float]:
    """(no-load rpm, stall torque N·m, stall current A, no-load current A) at ``volts``,
    using the linear DC-motor model scaled from the rated-voltage datasheet values."""
    k = volts / motor.spec("rated_v")
    return (motor.spec("no_load_rpm") * k, motor.spec("stall_torque_kgcm") * KGCM_TO_NM * k,
            motor.spec("stall_current_a") * k, motor.spec("no_load_current_a"))


def _current_at(stall_nm: float, stall_a: float, nl_a: float, torque_nm: float) -> float:
    if stall_nm <= 0:
        return stall_a
    return nl_a + (stall_a - nl_a) * min(torque_nm / stall_nm, 1.0)


def evaluate_drive(design: RoverDesign, motor: Component, driver: Component,
                   battery: Component) -> DriveOption:
    n = design.drive_motors
    per_channel = n // 2
    issues: list[str] = []

    if battery.spec("v_min") < driver.spec("v_min") or battery.spec("v_max") > driver.spec("v_max"):
        issues.append(f"{battery.name} ({battery.spec('v_min')}-{battery.spec('v_max')} V) is "
                      f"outside the {driver.name} motor supply range "
                      f"({driver.spec('v_min')}-{driver.spec('v_max')} V).")
    v_eff = max(battery.spec("v_nom") - driver.spec("drop_v"), 0.0)
    v_eff_max = max(battery.spec("v_max") - driver.spec("drop_v"), 0.0)
    if v_eff_max > motor.spec("v_max") * 1.1:
        issues.append(f"Motors would see up to {v_eff_max:.1f} V on a full battery - above their "
                      f"{motor.spec('v_max'):.0f} V rating.")
    if v_eff < 0.5 * motor.spec("rated_v"):
        issues.append(f"Only {v_eff:.1f} V reaches the {motor.spec('rated_v'):.0f} V motors - "
                      "far too little to perform.")

    total_mass = (design.chassis_mass + design.payload_mass + n * motor.mass_kg
                  + battery.mass_kg + driver.mass_kg + rover_mech.ELECTRONICS_MASS)
    loads = rover_mech.loads(design, total_mass)
    nl_rpm, stall_nm, stall_a, nl_a = _motor_curve(motor, v_eff)
    available = stall_nm * (1 - loads.wheel_rpm / nl_rpm) if nl_rpm > 0 else 0.0
    available = max(available, 0.0)
    run_a = _current_at(stall_nm, stall_a, nl_a, loads.load_torque_per_motor_nm)
    cruise_a = _current_at(stall_nm, stall_a, nl_a, loads.cruise_torque_per_motor_nm)

    if nl_rpm <= loads.wheel_rpm:
        issues.append(f"Top speed needs {loads.wheel_rpm:.0f} RPM but the motor only reaches "
                      f"{nl_rpm:.0f} RPM at {v_eff:.1f} V.")
    elif available < loads.torque_per_motor_nm:
        issues.append(f"Needs {to_kgcm(loads.torque_per_motor_nm):.2f} kg·cm at "
                      f"{loads.wheel_rpm:.0f} RPM; motor delivers {to_kgcm(available):.2f}.")
    if run_a * per_channel > driver.spec("continuous_a"):
        issues.append(f"{run_a * per_channel:.2f} A per channel exceeds the {driver.name}'s "
                      f"{driver.spec('continuous_a')} A continuous rating.")
    if n * run_a + LOGIC_CURRENT_A > battery.spec("max_a"):
        issues.append(f"Battery can only supply {battery.spec('max_a')} A.")

    option = DriveOption(
        motor=motor, driver=driver, battery=battery, loads=loads, v_eff=v_eff,
        v_eff_max=v_eff_max, no_load_rpm=nl_rpm, stall_nm=stall_nm, available_nm=available,
        run_current_a=run_a, cruise_current_a=cruise_a, stall_current_a=stall_a, n_motors=n,
        issues=issues,
    )
    cost = n * motor.price_usd + battery.price_usd + driver.price_usd
    penalty = 0.0
    headroom = nl_rpm / loads.wheel_rpm if loads.wheel_rpm > 0 else 1.0
    if headroom > 2.5:  # would waste most of the PWM range and speed resolution
        penalty += (headroom - 2.5) * 6.0
    util = option.utilisation
    if util < 0.3:  # heavily oversized motor
        penalty += (0.3 - util) * 30.0
    option.score = cost + penalty
    return option


def drivetrain_candidates(design: RoverDesign, catalog: Catalog) -> list[DriveOption]:
    drivers = (catalog.by_category("motor_driver") if design.motor_driver == "auto"
               else [catalog.get(design.motor_driver)])
    if design.power_source == "auto":
        batteries = [b for b in catalog.by_category("power_source")
                     if b.spec("kind") == "battery"]
    else:
        batteries = [catalog.get(design.power_source)]
    motors = catalog.by_category("dc_motor")
    return [evaluate_drive(design, m, d, b) for d in drivers for b in batteries for m in motors]


def select_drivetrain(design: RoverDesign,
                      catalog: Catalog) -> tuple[DriveOption, list[DriveOption]]:
    """Best feasible (motor, driver, battery) combination plus runner-up alternatives.

    When nothing is feasible the closest option is returned with its issues attached, so the
    UI can still render the design and explain what to change.
    """
    options = drivetrain_candidates(design, catalog)
    feasible = sorted((o for o in options if o.feasible), key=lambda o: o.score)
    if feasible:
        best = feasible[0]
        seen = {best.motor.id}
        alternatives = []
        for o in feasible[1:]:
            if o.motor.id not in seen:
                alternatives.append(o)
                seen.add(o.motor.id)
            if len(alternatives) == 2:
                break
        return best, alternatives

    def closeness(o: DriveOption) -> tuple:
        ratio = o.available_nm / o.loads.torque_per_motor_nm if o.loads.torque_per_motor_nm else 0
        return (len(o.issues), -min(ratio, 1.0), o.score)

    return min(options, key=closeness), []


def battery_runtime_min(option: DriveOption, n_motors: int, logic_a: float) -> float:
    capacity_ah = option.battery.spec("capacity_mah", 0) / 1000.0
    avg = n_motors * option.cruise_current_a + logic_a
    return float(np.inf) if avg <= 0 else capacity_ah * 0.8 / avg * 60.0
