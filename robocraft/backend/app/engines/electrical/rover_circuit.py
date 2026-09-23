"""Rover circuit: battery, motor driver, 5 V logic rail, sensor and safety rules."""

from app.catalog import Catalog, Component
from app.engines.electrical.netlist import (
    COL_DRIVER,
    COL_LOAD,
    COL_POWER,
    COL_SOURCE,
    Circuit,
)
from app.engines.electrical.selection import (
    DriveOption,
    battery_runtime_min,
    fuse_rating,
    select_regulator,
    to_kgcm,
    utilisation_status,
)
from app.schemas.design import RoverDesign

LOGIC_RAIL_V = 5.0
MIN_RUNTIME_MIN = 20.0

# Pin names per driver control scheme.
DRIVER_PINS = {
    "en_in": {
        "supply": "12V", "ground": "GND",
        "outputs": {"left": ("OUT1", "OUT2"), "right": ("OUT3", "OUT4")},
        # (signal key, MCU pin pool, driver pin); PWM signals first so they get PWM pins.
        "signals": [("ena", "pwm", "ENA"), ("enb", "pwm", "ENB"), ("in1", "digital", "IN1"),
                    ("in2", "digital", "IN2"), ("in3", "digital", "IN3"),
                    ("in4", "digital", "IN4")],
    },
    "pwm_in_stby": {
        "supply": "VM", "ground": "GND",
        "outputs": {"left": ("AO1", "AO2"), "right": ("BO1", "BO2")},
        "signals": [("pwma", "pwm", "PWMA"), ("pwmb", "pwm", "PWMB"), ("ain1", "digital", "AIN1"),
                    ("ain2", "digital", "AIN2"), ("bin1", "digital", "BIN1"),
                    ("bin2", "digital", "BIN2"), ("stby", "digital", "STBY")],
    },
    "pwm_dir": {
        "supply": "POWER+", "ground": "POWER-",
        "outputs": {"left": ("M1A", "M1B"), "right": ("M2A", "M2B")},
        "signals": [("pwm1", "pwm", "PWM1"), ("pwm2", "pwm", "PWM2"), ("dir1", "digital", "DIR1"),
                    ("dir2", "digital", "DIR2")],
    },
}


def drive_actuator(design: RoverDesign, option: DriveOption,
                   alternatives: list[DriveOption]) -> dict:
    loads = option.loads
    util = option.utilisation
    return {
        "role": "drive",
        "label": f"Drive motors ×{design.drive_motors}",
        "component_id": option.motor.id,
        "name": option.motor.name,
        "required_nm": loads.torque_per_motor_nm,
        "required_kgcm": to_kgcm(loads.torque_per_motor_nm),
        "available_nm": option.available_nm,
        "available_kgcm": to_kgcm(option.available_nm),
        "utilization": util,
        "status": utilisation_status(util) if option.feasible else "insufficient",
        "rationale": (
            f"At {option.v_eff:.1f} V the motor spins up to {option.no_load_rpm:.0f} RPM and "
            f"still delivers {to_kgcm(option.available_nm):.2f} kg·cm at the "
            f"{loads.wheel_rpm:.0f} RPM your top speed needs "
            f"({to_kgcm(loads.torque_per_motor_nm):.2f} kg·cm required incl. safety factor). "
            f"Chosen with a {option.driver.name} and a {option.battery.name} as the lowest-cost "
            "combination that passes every check."
        ) if option.feasible else " ".join(option.issues),
        "alternatives": [
            {"component_id": a.motor.id, "name": a.motor.name, "price_usd": a.motor.price_usd,
             "rating": f"{to_kgcm(a.available_nm):.2f} kg·cm @ {a.loads.wheel_rpm:.0f} RPM with "
                       f"{a.driver.name.split(' ')[0]} + {a.battery.name.split(' (')[0]}"}
            for a in alternatives
        ],
        "mass_kg": option.motor.mass_kg,
        "price_usd": option.motor.price_usd,
        "extra": {
            "no_load_rpm": option.no_load_rpm,
            "wheel_rpm": loads.wheel_rpm,
            "motor_voltage": option.v_eff,
            "run_current_a": option.run_current_a,
            "stall_current_a": option.stall_current_a,
            "driver_id": option.driver.id,
            "battery_id": option.battery.id,
        },
    }


def build_rover_circuit(design: RoverDesign, catalog: Catalog, board: Component,
                        option: DriveOption) -> dict:
    c = Circuit(catalog, board)
    mcu = c.mcu
    n = design.drive_motors
    battery, driver, motor = option.battery, option.driver, option.motor
    control = driver.spec("control")
    pins = DRIVER_PINS[control]
    sensor_c = catalog.get("hc-sr04") if design.obstacle_sensor else None
    logic_a = board.spec("current_a") + (sensor_c.spec("current_a") if sensor_c else 0.0)
    motor_peak = n * option.run_current_a

    # ---------------------------------------------------------------- power path
    bat = c.add(battery.id, prefix="BT", label=battery.name, column=COL_SOURCE,
                reason="Main battery for motors and logic")
    rating = fuse_rating(catalog, motor_peak + logic_a)
    fuse = c.add("fuse-inline", prefix="F", label=f"{rating:g} A fuse", column=COL_POWER,
                 reason="Protects battery and wiring from short circuits", auto_added=True,
                 note=f"Fit a {rating:g} A blade fuse")
    switch = c.add("switch-rocker", prefix="SW", label="Power switch", column=COL_POWER,
                   reason="Main kill switch", auto_added=True)
    c.wire(bat, "+", fuse, "IN", "VBAT", "power")
    c.wire(fuse, "OUT", switch, "IN", "VBAT", "power")
    c.check("battery-protection", "info", f"Added a {rating:g} A fuse and a power switch",
            "A shorted wire on a lithium pack can start a fire; the fuse blows first and the "
            "switch lets you stop a runaway rover.", auto_fixed=True)

    drv = c.add(driver.id, prefix="U", label=driver.name, column=COL_DRIVER,
                reason=f"Drives {n} DC motors ({option.motors_per_channel} per channel)")
    c.wire(switch, "OUT", drv, pins["supply"], "VBAT", "power")
    c.wire(bat, "-", drv, pins["ground"], "GND", "ground")

    onboard = driver.spec("onboard_5v")
    pack = battery.name.split(" (")[0]
    logic_ok = True
    if (onboard and battery.spec("v_max") <= onboard["max_input_v"]
            and battery.spec("v_nom") >= onboard["min_input_v"] and logic_a <= onboard["max_a"]):
        five, five_pin, five_capacity = drv, "5V", onboard["max_a"]
        five_source = f"{driver.name.split(' ')[0]} onboard regulator"
        detail = (f"{battery.name} stays below {onboard['max_input_v']:g} V, so the L298N's "
                  f"regulator can power the board ({logic_a:.2f} A of {onboard['max_a']} A). "
                  "Keep its 5V-EN jumper fitted.")
        if battery.spec("v_min") < onboard["min_input_v"]:
            # The 78M05 needs ~7 V in; a nearly flat pack drops below that.
            c.check("logic-rail", "info",
                    f"5 V logic from the L298N regulator - recharge at "
                    f"≈{onboard['min_input_v']:g} V",
                    f"{detail} The regulator needs about {onboard['min_input_v']:g} V in, so "
                    "once the pack runs low the board can brown out and reset.",
                    fix=f"Recharge when the pack reads ≈{onboard['min_input_v']:g} V.")
        else:
            c.check("logic-rail", "pass", "5 V logic from the driver's onboard regulator", detail)
    else:
        reg_c = select_regulator(catalog, battery, LOGIC_RAIL_V, max(logic_a, 0.5))
        if reg_c is None:
            # Keep a placeholder so the diagram stays complete, but flag that it can't work.
            logic_ok = False
            reg_c = catalog.get("buck-lm2596")
            c.check("logic-rail", "error", f"No regulator can make 5 V from a {pack}",
                    f"The pack delivers {battery.spec('v_min')}-{battery.spec('v_max')} V, but a "
                    f"buck converter needs about {reg_c.spec('dropout_v'):g} V more than the "
                    "5 V it outputs.", fix="Pick a 2S or 3S battery.")
        reg = c.add(reg_c.id, prefix="U", label="Buck -> 5 V", column=COL_POWER,
                    reason="Supplies the 5 V logic rail", auto_added=True,
                    note="Adjust output to 5.0 V before connecting the board")
        c.wire(switch, "OUT", reg, "IN+", "VBAT", "power")
        c.wire(bat, "-", reg, "IN-", "GND", "ground")
        five, five_pin, five_capacity = reg, "OUT+", reg_c.spec("continuous_a")
        five_source = reg_c.name
        if logic_ok:
            if onboard and battery.spec("v_max") > onboard["max_input_v"]:
                detail = (f"A full {pack} reaches {battery.spec('v_max')} V - above the "
                          f"{onboard['max_input_v']:g} V limit of the L298N's onboard regulator, "
                          "which would overheat. RoboCraft added a buck converter for the logic "
                          "rail instead.")
                fix = "Remove the L298N's 5V-EN jumper and set the buck output to 5.0 V."
            elif onboard:
                detail = (f"A {pack} is below the ≈{onboard['min_input_v']:g} V the L298N's "
                          "onboard regulator needs, so a buck converter supplies the logic.")
                fix = "Remove the L298N's 5V-EN jumper and set the buck output to 5.0 V."
            else:
                detail = (f"The {driver.name} has no 5 V output, so a buck converter supplies "
                          "the board and sensor.")
                fix = "Set the buck output to 5.0 V before connecting the board."
            c.check("logic-rail", "info", "Added a 5 V buck converter for the logic", detail,
                    fix=fix, auto_fixed=True)
    c.wire(five, five_pin, mcu, board.spec("power_pin"), "5V", "power")
    c.wire(drv, pins["ground"] if control != "pwm_dir" else "GND", mcu, "GND", "GND", "ground")

    # ---------------------------------------------------------------- motors
    for side in ("left", "right"):
        out_a, out_b = pins["outputs"][side]
        for k in range(n // 2):
            label = f"{side.title()} motor" + (f" ({('front', 'rear')[k]})" if n == 4 else "")
            m = c.add(motor.id, prefix="M", label=label, column=COL_LOAD,
                      reason=f"{side.title()}-side drive wheel")
            c.wire(drv, out_a, m, "+", f"MOTOR_{side.upper()}_A", "motor")
            c.wire(drv, out_b, m, "-", f"MOTOR_{side.upper()}_B", "motor")
            c.add("cap-100nf", prefix="C", label="100 nF", column=COL_LOAD,
                  reason="Soldered across motor terminals to suppress noise", auto_added=True,
                  in_diagram=False)
    c.check("noise-caps", "info", f"Added {n} × 100 nF motor noise capacitors",
            "Brushed motors spray electrical noise that can reset the board or corrupt sensor "
            "readings. Solder one across each motor's terminals.", auto_fixed=True)

    # ---------------------------------------------------------------- control signals
    for key, pool, driver_pin in pins["signals"]:
        label = c.allocate(pool, key)
        c.wire(mcu, label, drv, driver_pin, key.upper(), "signal")
    logic_v = board.spec("logic_v")
    if control == "pwm_in_stby":
        c.wire(mcu, board.spec("logic_pin"), drv, "VCC", "VLOGIC", "power")
        c.check("driver-logic", "pass",
                f"TB6612FNG logic powered at {logic_v:g} V",
                "Its VCC pin is tied to the board's logic supply so input thresholds match "
                "the board's signals.")
    else:
        vih = driver.spec("vih", 2.5)
        if logic_v >= vih:
            c.check("driver-logic", "pass",
                    f"{logic_v:g} V signals are compatible with the driver",
                    f"{driver.name} inputs read HIGH above {vih:g} V.")
        else:
            c.check("driver-logic", "warning", "Driver may not see the board's HIGH level",
                    f"Needs {vih:g} V, board outputs {logic_v:g} V.",
                    fix="Add a level shifter on the control lines.")
    if control == "en_in":
        c.check("l298n-jumpers", "info", "Remove the ENA / ENB jumpers",
                "L298N modules ship with jumpers that force full speed. Pull them off so the "
                "board's PWM pins can control speed.")

    # ---------------------------------------------------------------- sensor
    if sensor_c:
        s = c.add(sensor_c.id, prefix="S", label="Ultrasonic sensor", column=COL_LOAD,
                  reason="Obstacle detection (stops before collisions)")
        c.wire(five, five_pin, s, "VCC", "5V", "power")
        c.wire(mcu, "GND", s, "GND", "GND", "ground")
        trig = c.allocate("digital", "trig")
        c.wire(mcu, trig, s, "TRIG", "TRIG", "signal")
        echo = c.allocate("input", "echo")
        echo_v = sensor_c.spec("echo_voh")
        if echo_v > board.spec("input_max_v"):
            ls = c.add("level-shifter-4ch", prefix="U", label="Level shifter", column=COL_DRIVER,
                       reason=f"Steps the {echo_v:g} V ECHO signal down to {logic_v:g} V",
                       auto_added=True)
            c.wire(five, five_pin, ls, "HV", "5V", "power")
            c.wire(mcu, board.spec("logic_pin"), ls, "LV", "VLOGIC", "power")
            c.wire(mcu, "GND", ls, "GND", "GND", "ground")
            c.wire(s, "ECHO", ls, "HV1", "ECHO_5V", "signal")
            c.wire(ls, "LV1", mcu, echo, "ECHO", "signal")
            c.check("logic-level-echo", "info",
                    f"Added a logic level converter to protect the {board.name}",
                    f"The HC-SR04 answers with a {echo_v:g} V pulse on ECHO, but the "
                    f"{board.name}'s pins tolerate only {board.spec('input_max_v'):g} V. Wiring it "
                    "directly would damage the board.", auto_fixed=True)
        else:
            c.wire(s, "ECHO", mcu, echo, "ECHO", "signal")
            c.check("logic-level-echo", "pass", "Sensor ECHO is safe for this board",
                    f"{echo_v:g} V pulses are within the {board.name}'s input rating.")
        trig_vih = sensor_c.spec("trig_vih")
        if logic_v >= trig_vih:
            c.check("logic-level-trig", "pass", f"{logic_v:g} V TRIG pulses trigger the sensor",
                    f"HC-SR04 needs about {trig_vih:g} V on TRIG.")

    # ---------------------------------------------------------------- electrical rule checks
    loads = option.loads
    util = option.utilisation
    if option.feasible:
        severity = {"ok": "pass", "marginal": "warning"}.get(utilisation_status(util), "error")
        c.check("drive-torque", severity,
                f"{motor.name}: {util:.0%} of available torque at top speed",
                f"Each motor must give {to_kgcm(loads.torque_per_motor_nm):.2f} kg·cm at "
                f"{loads.wheel_rpm:.0f} RPM; it delivers {to_kgcm(option.available_nm):.2f} "
                f"kg·cm there (no-load {option.no_load_rpm:.0f} RPM at {option.v_eff:.1f} V).",
                fix=None if severity == "pass" else "Increase the safety margin with a stronger "
                "motor, bigger battery voltage or lower top speed.")
    for i, issue in enumerate(option.issues):
        c.check(f"drivetrain-{i}", "error", "Drivetrain can't meet the requirements", issue,
                fix="Lower the top speed, acceleration, slope or payload; or choose another "
                    "battery/driver.")

    per_channel_run = option.run_current_a * option.motors_per_channel
    per_channel_stall = option.stall_current_a * option.motors_per_channel
    if per_channel_run <= driver.spec("continuous_a"):
        if per_channel_stall <= driver.spec("peak_a"):
            c.check("driver-current", "pass", "Driver handles running and stall current",
                    f"{per_channel_run:.2f} A running / {per_channel_stall:.2f} A stall per "
                    f"channel vs {driver.spec('continuous_a')} A / {driver.spec('peak_a')} A "
                    "rating.")
        else:
            c.check("driver-current", "warning", "Stall current exceeds the driver's peak rating",
                    f"A stalled {'pair of motors' if option.motors_per_channel > 1 else 'motor'} "
                    f"draws {per_channel_stall:.1f} A per channel; the {driver.name} peaks at "
                    f"{driver.spec('peak_a')} A. The generated firmware ramps PWM (soft start) to "
                    "limit inrush current.", fix="Avoid stalling the wheels against obstacles.")
    if driver.spec("drop_v", 0) >= 1.0:
        c.check("driver-drop", "info", f"{driver.name.split(' ')[0]} loses about "
                f"{driver.spec('drop_v'):g} V", f"Motors see ≈{option.v_eff:.1f} V from the "
                f"{battery.spec('v_nom')} V battery (already accounted for in the motor sizing).")

    c.check("motor-voltage",
            "pass" if option.v_eff_max <= motor.spec("v_max") else "warning",
            f"Motors run at {option.v_eff:.1f} V ({option.v_eff_max:.1f} V fully charged)",
            f"{motor.name} is rated {motor.spec('v_min')}-{motor.spec('v_max')} V.")

    runtime = battery_runtime_min(option, n, logic_a)
    c.check("battery-runtime", "pass" if runtime >= MIN_RUNTIME_MIN else "warning",
            f"≈{runtime:.0f} min of continuous driving",
            f"{battery.spec('capacity_mah')} mAh at ≈{n * option.cruise_current_a + logic_a:.2f} A "
            "cruising on flat ground (80% usable capacity). Hills and stop-and-go shorten this.",
            fix=None if runtime >= MIN_RUNTIME_MIN else "Pick a larger battery.")
    if battery.spec("chemistry") in ("LiPo", "Li-ion"):
        c.check("lithium-care", "info", "Lithium battery care",
                "Charge only with a balance charger and stop driving when the pack drops to "
                f"≈{battery.spec('v_min')} V - over-discharging damages the cells.")
    c.check("common-ground", "pass", "Common ground across battery, driver and board",
            "All modules share one ground so control signals have a common reference.")
    c.check("pins", "pass", f"{len(c.pin_map)} control pins assigned",
            ", ".join(f"{k.upper()}: {v}" for k, v in c.pin_labels.items()))

    # ---------------------------------------------------------------- mechanical feasibility
    if loads.slips:
        c.check("traction", "warning", "Wheels will slip before reaching full thrust",
                f"Needs {loads.traction_required_n:.1f} N of grip but tyres provide about "
                f"{loads.traction_available_n:.1f} N on this surface.",
                fix="Reduce acceleration/slope, add weight over the drive wheels or use 4WD.",
                engine="mechanical")
    else:
        c.check("traction", "pass", "Tyres have enough grip",
                f"{loads.traction_required_n:.1f} N needed, ≈{loads.traction_available_n:.1f} N "
                "available.", engine="mechanical")

    c.rails = [
        {"name": "Battery", "voltage": battery.spec("v_nom"), "source": battery.name,
         "typical_a": n * option.cruise_current_a + logic_a, "peak_a": motor_peak + logic_a,
         "capacity_a": battery.spec("max_a"),
         "status": "ok" if motor_peak + logic_a <= battery.spec("max_a") else "error"},
        {"name": "Motor supply", "voltage": option.v_eff, "source": driver.name,
         "typical_a": n * option.cruise_current_a, "peak_a": motor_peak,
         "capacity_a": driver.spec("continuous_a") * driver.spec("channels"),
         "status": "ok" if per_channel_run <= driver.spec("continuous_a") else "error"},
        {"name": "Logic 5 V", "voltage": LOGIC_RAIL_V, "source": five_source,
         "typical_a": logic_a, "peak_a": logic_a, "capacity_a": five_capacity,
         "status": "ok" if logic_ok and logic_a <= five_capacity else "error"},
    ]
    result = c.to_dict()
    result.update({"power_source_id": battery.id, "driver_id": driver.id,
                   "driver_control": control, "runtime_min": runtime})
    return result
