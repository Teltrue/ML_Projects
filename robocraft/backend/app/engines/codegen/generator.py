"""Code Generation Brain: turns a design and its analysis into ready-to-flash firmware.

The generated code uses the exact pins chosen by the Electrical Engine, the geometry and
limits from the Mechanical Engine and the same motion maths (IK, ramps, demo programs) as
the browser simulation, so the physical robot behaves like the one on screen.
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.catalog import Catalog
from app.engines.mechanical import arm, rover
from app.pipeline import analyze, resolve_board
from app.schemas.design import ArmDesign, RoverDesign

TEMPLATE_DIR = Path(__file__).parent / "templates"
LANGUAGES = {"arduino": ("Arduino C++", ".ino"), "micropython": ("MicroPython", ".py")}
GRIPPER_OPEN_DEG = 30.0
GRIPPER_CLOSED_DEG = 110.0

SERVO_HEADER = {"avr": "Servo.h", "esp32": "ESP32Servo.h", "rp2040": "Servo.h"}
CORE_SETUP = {
    "avr": "Arduino IDE: Tools > Board > Arduino AVR Boards > {board}.",
    "esp32": "Install the 'esp32' board package (Boards Manager), then pick 'ESP32 Dev Module'.",
    "rp2040": "Install Earle Philhower's 'Raspberry Pi Pico/RP2040' board package, then pick "
              "'Raspberry Pi Pico'.",
}
ARM_LIBRARIES = {
    "avr": ["Servo (bundled with the Arduino IDE)"],
    "esp32": ["ESP32Servo by Kevin Harrington (Library Manager)"],
    "rp2040": ["Servo (bundled with the RP2040 core)"],
}


class CodegenError(ValueError):
    pass


_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)
_env.filters["f"] = lambda value, digits=3: f"{float(value):.{digits}f}"


def _slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return slug or "robocraft_robot"


def _arm_context(design: ArmDesign, catalog: Catalog, analysis: dict) -> dict:
    elec = analysis["electrical"]
    servos = []
    for act in elec["actuators"]:
        comp = catalog.get(act["component_id"])
        key = f"servo_{act['role']}"
        servos.append({
            "role": act["role"], "label": act["label"], "name": comp.name,
            "pin": elec["pin_map"][key], "pin_label": elec["pin_labels"][key],
            "pulse_min": comp.spec("pulse_min_us"), "pulse_max": comp.spec("pulse_max_us"),
        })
    demo = []
    for wp in arm.demo_waypoints(design):
        pos = wp.position or arm.forward(design, wp.joints_deg)["ee"]
        demo.append({"label": wp.label, "home": wp.joints_deg is not None,
                     "grip": wp.gripper >= 0.5, "x": pos[0] * 1000, "y": pos[1] * 1000,
                     "z": pos[2] * 1000})
    rail = next(r for r in elec["rails"] if r["name"] == "Servo rail")
    return {
        "servos": servos,
        "demo": demo,
        "base_height": design.base_height,
        "upper_arm": design.upper_arm_length,
        "forearm": design.forearm_length,
        "max_speed": design.max_joint_speed,
        "max_accel": design.max_joint_accel,
        "limits": arm.JOINT_LIMITS_DEG,
        "offsets": arm.SERVO_OFFSET_DEG,
        "dirs": arm.SERVO_DIR,
        "home": arm.HOME_DEG,
        "gripper_open": GRIPPER_OPEN_DEG,
        "gripper_closed": GRIPPER_CLOSED_DEG,
        "rail_v": rail["voltage"],
    }


def _rover_context(design: RoverDesign, catalog: Catalog, analysis: dict, preset: str) -> dict:
    elec = analysis["electrical"]
    mech = analysis["mechanical"]
    driver = catalog.get(elec["driver_id"])
    motor = catalog.get(elec["actuators"][0]["component_id"])
    program = [{"label": s.label, "left": s.left, "right": s.right,
                "ms": int(round(s.duration * 1000))}
               for s in rover.preset_program(design, preset)]
    return {
        "control": elec["driver_control"],
        "driver_name": driver.name,
        "motor_name": motor.name,
        "motors": design.drive_motors,
        "pins": elec["pin_map"],
        "pin_labels": elec["pin_labels"],
        "wheel_diameter": design.wheel_diameter,
        "track_width": design.track_width,
        "top_speed": design.max_speed,
        "motor_max_speed": max(mech["motor_top_speed_mps"], 0.01),
        "max_accel": design.max_accel,
        "sensor": design.obstacle_sensor,
        "stop_cm": (mech["obstacle_stop_m"] or 0.0) * 100,
        "preset": preset,
        "preset_description": rover.PRESETS[preset],
        "program": program,
    }


def generate(design: ArmDesign | RoverDesign, catalog: Catalog, language: str,
             preset: str = "square") -> dict:
    if language not in LANGUAGES:
        raise CodegenError(f"Unsupported language '{language}'")
    board = resolve_board(design.board, catalog)
    if language not in board.spec("languages", []):
        raise CodegenError(f"{LANGUAGES[language][0]} isn't available for the {board.name}. "
                           "Pick an ESP32 or Raspberry Pi Pico to use MicroPython.")
    if isinstance(design, RoverDesign) and preset not in rover.PRESETS:
        raise CodegenError(f"Unknown demo program '{preset}'")

    analysis = analyze(design, catalog)
    core = board.spec("arduino_core")
    context = {
        "name": design.name,
        "board_name": board.name,
        "board_id": board.id,
        "core": core,
        "logic_v": board.spec("logic_v"),
        "servo_header": SERVO_HEADER.get(core, "Servo.h"),
    }
    if isinstance(design, ArmDesign):
        context.update(_arm_context(design, catalog, analysis))
        libraries = ARM_LIBRARIES.get(core, []) if language == "arduino" else []
    else:
        context.update(_rover_context(design, catalog, analysis, preset))
        libraries = []

    label, ext = LANGUAGES[language]
    code = _env.get_template(f"{design.template}_{language}{ext}.j2").render(**context)
    stem = _slug(design.name)
    if language == "arduino":
        filename = f"{stem}{ext}"
        instructions = [
            f"Create a folder named '{stem}' and save this file inside it as '{filename}'.",
            CORE_SETUP.get(core, "").format(board=board.name),
            *[f"Install library: {lib}" for lib in libraries],
            "Wire everything exactly as shown in the Electronics tab, then upload.",
            "Open the Serial Monitor at 115200 baud (newline line ending) and follow the prompt.",
        ]
    else:
        filename = "main.py"
        instructions = [
            f"Flash the MicroPython firmware for the {board.name} (micropython.org/download).",
            "Copy this file to the board as main.py (Thonny: File > Save as > MicroPython device).",
            "Wire everything exactly as shown in the Electronics tab, then reset the board.",
            "Type commands into the REPL / serial console (115200 baud).",
        ]
    checks = analysis["mechanical"]["checks"] + analysis["electrical"]["checks"]
    blocking = [c["title"] for c in checks if c["severity"] == "error"]
    return {
        "language": language,
        "language_label": label,
        "filename": filename,
        "board": board.name,
        "code": code,
        "libraries": libraries,
        "instructions": [i for i in instructions if i],
        "warnings": blocking,
    }
