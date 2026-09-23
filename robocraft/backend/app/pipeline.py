"""Orchestrates the engines: Mechanical -> Electrical (-> Code generation on demand).

The Mechanical Engine sizes torques, the Electrical Engine picks parts for them, and the
chosen parts' masses are fed back into the mechanics until the selection is stable (a
heavier elbow servo loads the shoulder, which may need a bigger servo, and so on).
"""

import math

from app.catalog import Catalog, CatalogError, Component
from app.engines.electrical.arm_circuit import build_arm_circuit, plan_servo_power
from app.engines.electrical.netlist import Check, PinAllocationError
from app.engines.electrical.rover_circuit import build_rover_circuit, drive_actuator
from app.engines.electrical.selection import select_drivetrain, select_servo, to_kgcm
from app.engines.mechanical import arm, rover
from app.schemas.design import ArmDesign, RoverDesign

MAX_SIZING_ITERATIONS = 8
STOP_MARGIN_M = 0.10


class DesignError(ValueError):
    """The design references something invalid (unknown board, wrong kind of part...)."""


def resolve_board(board_id: str, catalog: Catalog) -> Component:
    try:
        board = catalog.get(board_id)
    except CatalogError as exc:
        raise DesignError(f"Unknown microcontroller '{board_id}'") from exc
    if board.category != "microcontroller":
        raise DesignError(f"'{board_id}' is not a microcontroller")
    return board


def _check_power_source(power_source: str, catalog: Catalog, allowed_kinds: set[str]) -> None:
    if power_source == "auto":
        return
    try:
        src = catalog.get(power_source)
    except CatalogError as exc:
        raise DesignError(f"Unknown power source '{power_source}'") from exc
    if src.category != "power_source" or src.spec("kind") not in allowed_kinds:
        raise DesignError(f"'{power_source}' can't power this template")


def _summary(checks: list[dict], cost: float, mass: float, extra: dict) -> dict:
    counts = {k: sum(c["severity"] == k for c in checks) for k in ("pass", "info", "warning",
                                                                      "error")}
    auto_fixes = sum(bool(c.get("auto_fixed")) for c in checks)
    if counts["error"]:
        status, headline = "error", f"{counts['error']} blocking issue(s) - see checks"
    elif counts["warning"]:
        status, headline = "warning", f"Buildable, with {counts['warning']} warning(s)"
    else:
        status, headline = "ok", "Design is feasible and electrically safe"
    return {"status": status, "headline": headline, "total_cost_usd": cost,
            "total_mass_kg": mass, "check_counts": counts, "auto_fixes": auto_fixes, **extra}


def _as_dicts(checks: list[Check]) -> list[dict]:
    return [c.__dict__ for c in checks]


# --------------------------------------------------------------------------- arm


def analyze_arm(design: ArmDesign, catalog: Catalog) -> dict:
    board = resolve_board(design.board, catalog)
    _check_power_source(design.power_source, catalog, {"adapter", "battery"})
    power = plan_servo_power(design, catalog)
    coeffs = arm.load_coefficients(design)

    masses = arm.ActuatorMasses()
    for _ in range(MAX_SIZING_ITERATIONS):
        loads = arm.joint_loads(design, masses, coeffs)
        selections = [select_servo(ld.name, ld.label, ld.required_nm, power.rail_v, catalog)
                      for ld in loads]
        selections.append(select_servo("gripper", "Gripper", arm.gripper_torque(design),
                                       power.rail_v, catalog))
        new_masses = arm.ActuatorMasses(*(s.component.mass_kg for s in selections))
        if new_masses == masses:
            break
        masses = new_masses

    available = [s.available_nm for s in selections[:3]]
    payload_limit = arm.max_payload(design, masses, available, coeffs)
    home = arm.stability(design, masses, list(arm.HOME_DEG))
    extended = arm.stability(design, masses, [0.0, 0.0, 0.0])
    rch = arm.reach(design)

    mech_checks: list[Check] = []
    if extended["stable"]:
        offset_mm = extended["horizontal_offset_m"] * 1000
        mech_checks.append(Check("stability", "pass", "Won't tip over at full reach",
                                 f"Centre of mass stays {offset_mm:.0f} mm from the axis, inside "
                                 f"the {design.base_radius * 1000:.0f} mm footprint.",
                                 engine="mechanical"))
    else:
        mech_checks.append(Check(
            "stability", "warning", "Arm tips over when fully extended",
            f"With the payload at full reach the centre of mass sits "
            f"{extended['horizontal_offset_m'] * 1000:.0f} mm out - beyond the "
            f"{design.base_radius * 1000:.0f} mm base.",
            fix=f"Clamp the base to the table, widen it, or add "
                f"{math.ceil(extended['ballast_kg'] * 1000):.0f} g of ballast.",
            engine="mechanical"))
    if payload_limit >= design.payload_mass:
        mech_checks.append(Check("payload", "pass",
                                 f"Can lift up to ≈{payload_limit * 1000:.0f} g with these servos",
                                 f"Your payload is {design.payload_mass * 1000:.0f} g "
                                 f"(safety factor {design.safety_factor:g}× included).",
                                 engine="mechanical"))
    else:
        mech_checks.append(Check("payload", "error", "Payload exceeds what the servos can hold",
                                 f"Selected servos support ≈{payload_limit * 1000:.0f} g but the "
                                 f"design asks for {design.payload_mass * 1000:.0f} g.",
                                 fix="Shorten the links or reduce the payload.",
                                 engine="mechanical"))
    mech_checks.append(Check("base-bearing", "info", "Carry the arm on a turntable bearing",
                             "Mount the rotating platform on a lazy-susan bearing so the base "
                             "servo only turns the arm instead of holding its weight on its "
                             "shaft.", engine="mechanical"))
    ratio = design.upper_arm_length / design.forearm_length
    if not 0.6 <= ratio <= 1.7:
        mech_checks.append(Check("link-ratio", "info", "Unequal links leave a blind spot",
                                 f"The arm can't reach within {rch['min'] * 1000:.0f} mm of its "
                                 "shoulder. Similar link lengths give the most useful workspace.",
                                 engine="mechanical"))
    mech_checks.append(Check("reach", "info",
                             f"Reach: {rch['max'] * 1000:.0f} mm from the shoulder",
                             f"Shoulder axis {design.base_height * 1000:.0f} mm above the table.",
                             engine="mechanical"))

    try:
        electrical = build_arm_circuit(design, catalog, board, selections, power)
    except PinAllocationError as exc:
        raise DesignError(str(exc)) from exc
    electrical["actuators"] = [s.to_dict() for s in selections]

    joints = []
    for ld, lim in zip(loads, arm.JOINT_LIMITS_DEG, strict=True):
        joints.append({
            "name": ld.name, "label": ld.label, "gravity_nm": ld.gravity_nm,
            "inertial_nm": ld.inertial_nm, "required_nm": ld.required_nm,
            "required_kgcm": to_kgcm(ld.required_nm), "worst_pose_deg": list(ld.worst_pose_deg),
            "limits_deg": list(lim),
        })
    joints.append({
        "name": "gripper", "label": "Gripper", "gravity_nm": 0.0, "inertial_nm": 0.0,
        "required_nm": arm.gripper_torque(design),
        "required_kgcm": to_kgcm(arm.gripper_torque(design)), "worst_pose_deg": [],
        "limits_deg": [0.0, 180.0],
    })

    mechanical = {
        "template": "arm",
        "dh_table": arm.dh_table(design),
        "joints": joints,
        "reach": rch,
        "home_deg": list(arm.HOME_DEG),
        "max_payload_kg": payload_limit,
        "actuator_masses_kg": masses.__dict__,
        "moving_mass_kg": sum(b.mass for b in arm.moving_bodies(design, masses)),
        "stability": {"home": home, "extended": extended},
        "checks": _as_dicts(mech_checks),
    }
    checks = mechanical["checks"] + electrical["checks"]
    total_mass = home["total_mass_kg"]
    return {
        "template": "arm",
        "name": design.name,
        "mechanical": mechanical,
        "electrical": electrical,
        "summary": _summary(checks, electrical["total_cost_usd"], total_mass,
                            {"servos": len(selections)}),
    }


# --------------------------------------------------------------------------- rover


def obstacle_stop_distance_m(design: RoverDesign) -> float:
    braking = rover.kinematics(design)["stopping_distance_m"]
    return min(max(braking + STOP_MARGIN_M, 0.15), 1.5)


def analyze_rover(design: RoverDesign, catalog: Catalog) -> dict:
    board = resolve_board(design.board, catalog)
    _check_power_source(design.power_source, catalog, {"battery"})
    option, alternatives = select_drivetrain(design, catalog)
    loads = option.loads
    kin = rover.kinematics(design)

    mech_checks: list[Check] = []
    wheel_width = min(0.25 * design.wheel_diameter + 0.01, 0.06)
    if design.track_width < design.chassis_width + wheel_width:
        mech_checks.append(Check(
            "track-width", "info", "Wheels overlap the chassis",
            f"A {design.track_width * 1000:.0f} mm track with a {design.chassis_width * 1000:.0f}"
            " mm chassis needs wheel cut-outs.", fix="Widen the track or narrow the chassis.",
            engine="mechanical"))
    mech_checks.append(Check(
        "braking", "info", f"Stops in ≈{kin['stopping_distance_m'] * 100:.0f} cm from top speed",
        f"At {design.max_accel:g} m/s² deceleration."
        + (f" The obstacle sensor triggers a stop at "
           f"{obstacle_stop_distance_m(design) * 100:.0f} cm." if design.obstacle_sensor else ""),
        engine="mechanical"))

    try:
        electrical = build_rover_circuit(design, catalog, board, option)
    except PinAllocationError as exc:
        raise DesignError(str(exc)) from exc
    electrical["actuators"] = [drive_actuator(design, option, alternatives)]

    n = design.drive_motors
    mechanical = {
        "template": "rover",
        "total_mass_kg": loads.total_mass,
        "mass_breakdown_kg": {
            "chassis": design.chassis_mass, "payload": design.payload_mass,
            "motors": n * option.motor.mass_kg, "battery": option.battery.mass_kg,
            "driver": option.driver.mass_kg, "electronics": rover.ELECTRONICS_MASS,
        },
        "forces_n": {"rolling": loads.rolling_n, "grade": loads.grade_n,
                     "acceleration": loads.accel_n, "total": loads.total_n},
        "wheel_rpm": loads.wheel_rpm,
        "torque_per_motor_nm": loads.torque_per_motor_nm,
        "torque_per_motor_kgcm": to_kgcm(loads.torque_per_motor_nm),
        "power_per_motor_w": loads.power_per_motor_w,
        "traction": {"required_n": loads.traction_required_n,
                     "available_n": loads.traction_available_n, "ok": not loads.slips},
        "kinematics": kin,
        "motor_top_speed_mps": motor_top_speed(design, option.no_load_rpm),
        "obstacle_stop_m": obstacle_stop_distance_m(design) if design.obstacle_sensor else None,
        "checks": _as_dicts(mech_checks),
    }
    # Traction is computed with the final mass, so the circuit builder reports it; move it
    # to the mechanical list where it belongs.
    for chk in [c for c in electrical["checks"] if c["engine"] == "mechanical"]:
        electrical["checks"].remove(chk)
        mechanical["checks"].append(chk)
    checks = mechanical["checks"] + electrical["checks"]
    return {
        "template": "rover",
        "name": design.name,
        "mechanical": mechanical,
        "electrical": electrical,
        "summary": _summary(checks, electrical["total_cost_usd"], loads.total_mass,
                            {"motors": n, "runtime_min": electrical.get("runtime_min")}),
    }


def motor_top_speed(design: RoverDesign, no_load_rpm: float, load_factor: float = 0.85) -> float:
    """Estimated wheel surface speed at 100% PWM, used to map m/s commands to duty cycle."""
    return no_load_rpm * load_factor * math.pi * design.wheel_diameter / 60.0


def analyze(design: ArmDesign | RoverDesign, catalog: Catalog) -> dict:
    if isinstance(design, ArmDesign):
        return analyze_arm(design, catalog)
    return analyze_rover(design, catalog)
