"""Arm circuit: dedicated servo power rail, signal wiring and safety rules."""

from dataclasses import dataclass

from app.catalog import Catalog, Component
from app.engines.electrical.netlist import COL_LOAD, COL_POWER, COL_SOURCE, Circuit
from app.engines.electrical.selection import Selection, fuse_rating, select_regulator, to_kgcm
from app.schemas.design import ArmDesign

SERVO_RAIL_V = 6.0
SERVO_RAIL_MIN_V = 4.8
BUCK_DROPOUT_V = 1.2
BOARD_5V_PIN_LIMIT_A = 0.5


@dataclass(frozen=True)
class ServoPower:
    source: Component
    rail_v: float
    regulated: bool
    compatible: bool
    reason: str = ""


def plan_servo_power(design: ArmDesign, catalog: Catalog) -> ServoPower:
    """Decide the servo rail voltage *before* sizing servos (torque depends on voltage)."""
    if design.power_source == "auto":
        return ServoPower(catalog.get("psu-6v-5a"), SERVO_RAIL_V, False, True)
    src = catalog.get(design.power_source)
    v_min, v_nom, v_max = src.spec("v_min"), src.spec("v_nom"), src.spec("v_max")
    if src.spec("kind") == "usb":
        return ServoPower(src, v_nom, False, False,
                          "USB can't supply servo current; pick a dedicated supply.")
    if v_nom >= SERVO_RAIL_MIN_V and v_max <= SERVO_RAIL_V + 1e-9:
        return ServoPower(src, v_nom, False, True)
    # A buck converter holds 6 V at nominal charge and stays above the servos' minimum
    # voltage even as the source sags towards empty.
    if v_nom - BUCK_DROPOUT_V >= SERVO_RAIL_V and v_min - BUCK_DROPOUT_V >= SERVO_RAIL_MIN_V:
        return ServoPower(src, SERVO_RAIL_V, True, True)
    return ServoPower(src, src.spec("v_nom"), False, False,
                      f"{src.name} ({v_min}-{v_max} V) can't feed a 4.8-6 V servo rail directly "
                      "and is too low to regulate down.")


def servo_currents(selections: list[Selection]) -> tuple[float, float, float]:
    """(typical while moving, design current, all-stalled peak) in amps."""
    stalls = [s.component.spec("stall_current_a") for s in selections]
    peak = sum(stalls)
    return 0.3 * peak, max(0.5 * peak, max(stalls)), peak


def _auto_supply(catalog: Catalog, design_a: float) -> Component:
    adapters = sorted((c for c in catalog.by_category("power_source")
                       if c.spec("kind") == "adapter" and c.spec("v_nom") == SERVO_RAIL_V),
                      key=lambda c: c.spec("max_a"))
    return next((c for c in adapters if c.spec("max_a") >= design_a), adapters[-1])


def build_arm_circuit(design: ArmDesign, catalog: Catalog, board: Component,
                      selections: list[Selection], power: ServoPower) -> dict:
    c = Circuit(catalog, board)
    mcu = c.mcu
    typical_a, design_a, peak_a = servo_currents(selections)
    rail_v = power.rail_v

    usb = c.add("usb-power", prefix="J", label="USB 5 V", column=COL_SOURCE,
                reason="Powers the microcontroller logic (never the servos)")
    c.wire(usb, "5V", mcu, "USB", "USB_5V", "power")

    source = _auto_supply(catalog, design_a) if design.power_source == "auto" else power.source
    is_battery = source.spec("kind") == "battery"
    src = c.add(source.id, prefix="BT" if is_battery else "PS", label=source.name,
                column=COL_SOURCE, reason=f"Dedicated {rail_v:.1f} V servo supply")
    pos, pos_pin = src, "+"
    gnd, gnd_pin = src, "-"

    if is_battery:
        rating = fuse_rating(catalog, design_a)
        fuse = c.add("fuse-inline", prefix="F", label=f"{rating:g} A fuse", column=COL_POWER,
                     reason="Protects the battery and wiring from short circuits",
                     auto_added=True, note=f"Fit a {rating:g} A blade fuse")
        switch = c.add("switch-rocker", prefix="SW", label="Power switch", column=COL_POWER,
                       reason="Cuts servo power instantly", auto_added=True)
        c.wire(pos, pos_pin, fuse, "IN", "VBAT", "power")
        c.wire(fuse, "OUT", switch, "IN", "VBAT", "power")
        pos, pos_pin = switch, "OUT"
        c.check("battery-protection", "info", f"Added a {rating:g} A fuse and a power switch",
                "Batteries can deliver dangerous short-circuit currents; the fuse protects the "
                "wiring and the switch lets you kill servo power instantly.", auto_fixed=True)

    capacity = source.spec("max_a")
    if power.regulated:
        reg_c = select_regulator(catalog, source, rail_v, design_a)
        if reg_c is None:
            reg_c = max(catalog.by_category("regulator"), key=lambda r: r.spec("continuous_a"))
            c.check("servo-regulator", "error", "No regulator can supply the servo current",
                    f"The servos need about {design_a:.1f} A; the largest buck converter in the "
                    f"library supplies {reg_c.spec('continuous_a')} A.",
                    fix="Use smaller servos or a 6 V bench supply.")
        reg = c.add(reg_c.id, prefix="U", label=f"Buck -> {rail_v:.1f} V", column=COL_POWER,
                    reason=f"Steps {source.spec('v_nom')} V down to a {rail_v:.1f} V servo rail",
                    auto_added=True, note=f"Adjust output to {rail_v:.1f} V before connecting")
        c.wire(pos, pos_pin, reg, "IN+", "VBAT", "power")
        c.wire(gnd, gnd_pin, reg, "IN-", "GND", "ground")
        pos, pos_pin, gnd, gnd_pin = reg, "OUT+", reg, "OUT-"
        capacity = min(capacity, reg_c.spec("continuous_a"))
        c.check("servo-regulator-added", "info",
                f"Added a {reg_c.name} to make a {rail_v:.1f} V servo rail",
                f"{source.name} reaches {source.spec('v_max')} V, which would destroy "
                f"{min(s.component.spec('v_max') for s in selections):.1f} V servos.",
                fix=f"Turn the trim pot until the output reads {rail_v:.1f} V *before* plugging "
                    "in any servo.", auto_fixed=True)

    cap = c.add("cap-1000uf", prefix="C", label="1000 µF", column=COL_POWER,
                reason="Smooths servo current spikes that could reset the board",
                auto_added=True, note="Mind the polarity: stripe = negative")
    c.wire(pos, pos_pin, cap, "+", "V_SERVO", "power")
    c.wire(gnd, gnd_pin, cap, "-", "GND", "ground")

    for sel in selections:
        servo = c.add(sel.component.id, prefix="M", label=f"{sel.label} servo", column=COL_LOAD,
                      reason=f"{sel.label} joint - {to_kgcm(sel.required_nm):.2f} kg·cm needed")
        pin = c.allocate("pwm", f"servo_{sel.role}")
        c.wire(pos, pos_pin, servo, "V+", "V_SERVO", "power")
        c.wire(gnd, gnd_pin, servo, "GND", "GND", "ground")
        c.wire(mcu, pin, servo, "SIG", f"SERVO_{sel.role.upper()}", "signal")
    c.wire(gnd, gnd_pin, mcu, "GND", "GND", "ground")

    # ---------------------------------------------------------------- rule checks
    for sel in selections:
        status = sel.status
        severity = {"ok": "pass", "marginal": "warning", "insufficient": "error"}[status]
        c.check(
            f"servo-torque-{sel.role}", severity,
            f"{sel.label}: {sel.component.name} at {sel.utilisation:.0%} of stall torque",
            sel.rationale,
            fix=None if status == "ok" else
            "Shorten the links, lighten the payload, lower the acceleration or pick a "
            "stronger servo.",
        )

    c.check("servo-power-isolation", "info", "Servos get their own power supply",
            f"Together the servos can draw {peak_a:.1f} A when stalled. The board's 5 V pin "
            f"supplies about {BOARD_5V_PIN_LIMIT_A} A - powering servos from it would brown out "
            "or burn the board, so RoboCraft wired a separate servo rail.", auto_fixed=True)

    if power.compatible:
        bad = [s for s in selections
               if not s.component.spec("v_min") <= rail_v <= s.component.spec("v_max")]
        if bad:
            c.check("servo-rail-voltage", "error", f"{rail_v:.1f} V rail is outside servo ratings",
                    ", ".join(f"{s.component.name} needs {s.component.spec('v_min')}-"
                              f"{s.component.spec('v_max')} V" for s in bad))
        else:
            c.check("servo-rail-voltage", "pass", f"{rail_v:.1f} V servo rail suits every servo",
                    "Each servo is operated inside its rated voltage range.")
    else:
        c.check("servo-rail-voltage", "error", "Power source can't run the servos", power.reason,
                fix="Choose a 6 V supply, a 4x AA pack, or a 2S/3S pack (a regulator is added).")

    if capacity >= peak_a:
        c.check("servo-supply-current", "pass", f"Supply covers the {peak_a:.1f} A worst case",
                f"{capacity:g} A available vs {peak_a:.1f} A if every servo stalls at once.")
    elif capacity >= design_a:
        c.check("servo-supply-current", "pass", f"Supply covers normal operation ({capacity:g} A)",
                f"About {design_a:.1f} A is needed while moving. Only if every servo stalled at "
                f"once ({peak_a:.1f} A) could the rail dip - avoid driving joints into hard stops.")
    else:
        c.check("servo-supply-current", "error", "Servo supply is too small",
                f"{capacity:g} A available but about {design_a:.1f} A is needed.",
                fix="Pick a higher-current supply.")

    c.check("bulk-capacitor", "info", "Added a 1000 µF capacitor on the servo rail",
            "Servos draw sharp current spikes; the capacitor stops them from resetting the "
            "controller.", auto_fixed=True)
    c.check("common-ground", "pass", "Common ground between supply and board",
            "Servo signals are measured against ground, so the supply's negative is tied to "
            "the board's GND.")

    logic_v = board.spec("logic_v")
    worst_vih = max(s.component.spec("signal_vih", 2.5) for s in selections)
    if logic_v >= worst_vih:
        c.check("logic-level", "pass", f"{logic_v:g} V control signals drive every servo",
                f"The servos register a HIGH above about {worst_vih:g} V.")
    else:
        c.check("logic-level", "warning", "Servo signal may be too weak",
                f"Servos need about {worst_vih:g} V, the board outputs {logic_v:g} V.",
                fix="Add a 74AHCT125 buffer on the signal lines.")

    c.check("logic-power", "info", "Board runs from USB",
            "For standalone use, power the board from its own 5 V source (not the servo rail).")
    c.check("pins", "pass", f"{len(selections)} PWM pins assigned",
            ", ".join(f"{s.label}: {c.pin_labels[f'servo_{s.role}']}" for s in selections))

    rail_status = "ok" if capacity >= design_a else "error"
    c.rails = [
        {"name": "Servo rail", "voltage": rail_v, "source": source.name, "typical_a": typical_a,
         "peak_a": peak_a, "capacity_a": capacity, "status": rail_status},
        {"name": "Logic (USB)", "voltage": 5.0, "source": "USB",
         "typical_a": board.spec("current_a"), "peak_a": board.spec("current_a"),
         "capacity_a": BOARD_5V_PIN_LIMIT_A, "status": "ok"},
    ]
    result = c.to_dict()
    result["power_source_id"] = source.id
    return result
