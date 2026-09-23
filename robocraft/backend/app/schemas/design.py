"""User-editable design parameters for each template.

Every field carries ``ui`` metadata (label, unit, group, slider range, display scale) so the
frontend can render its parameter panel directly from ``GET /api/templates`` and the valid
ranges only live in one place. Internally everything is SI: metres, kilograms, seconds;
angles are exposed in degrees.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def param(
    default: float,
    *,
    lo: float,
    hi: float,
    step: float,
    label: str,
    unit: str,
    group: str,
    scale: float = 1.0,
    help: str = "",
) -> Any:
    """Numeric parameter rendered as a slider. ``scale`` converts SI to the display unit."""
    return Field(
        default,
        ge=lo,
        le=hi,
        description=help,
        json_schema_extra={
            "ui": {
                "kind": "slider",
                "label": label,
                "unit": unit,
                "group": group,
                "min": lo,
                "max": hi,
                "step": step,
                "scale": scale,
            }
        },
    )


def choice(
    default: Any,
    *,
    label: str,
    group: str,
    options: list[dict[str, Any]] | None = None,
    options_from: str | None = None,
    help: str = "",
) -> Any:
    """Parameter rendered as a dropdown. ``options_from`` names a catalog query."""
    return Field(
        default,
        description=help,
        json_schema_extra={
            "ui": {
                "kind": "select",
                "label": label,
                "group": group,
                "options": options or [],
                "options_from": options_from,
            }
        },
    )


def toggle(default: bool, *, label: str, group: str, help: str = "") -> Any:
    return Field(
        default,
        description=help,
        json_schema_extra={"ui": {"kind": "toggle", "label": label, "group": group}},
    )


class ArmDesign(BaseModel):
    """3-axis (yaw / shoulder pitch / elbow pitch) servo arm with a gripper."""

    model_config = ConfigDict(extra="forbid")

    template: Literal["arm"] = "arm"
    name: str = Field("My 3-Axis Arm", min_length=1, max_length=80)

    base_height: float = param(
        0.10, lo=0.04, hi=0.40, step=0.005, label="Shoulder height", unit="mm", scale=1000,
        group="Geometry", help="Height of the shoulder axis above the table.",
    )
    upper_arm_length: float = param(
        0.12, lo=0.05, hi=0.40, step=0.005, label="Upper arm length", unit="mm", scale=1000,
        group="Geometry", help="Shoulder axis to elbow axis.",
    )
    forearm_length: float = param(
        0.12, lo=0.05, hi=0.40, step=0.005, label="Forearm length", unit="mm", scale=1000,
        group="Geometry", help="Elbow axis to the gripping point.",
    )
    base_radius: float = param(
        0.07, lo=0.03, hi=0.25, step=0.005, label="Base footprint radius", unit="mm",
        scale=1000, group="Geometry", help="Used for the tip-over (stability) check.",
    )

    upper_arm_mass: float = param(
        0.060, lo=0.005, hi=1.5, step=0.005, label="Upper arm mass", unit="g", scale=1000,
        group="Mass & payload",
    )
    forearm_mass: float = param(
        0.045, lo=0.005, hi=1.5, step=0.005, label="Forearm mass", unit="g", scale=1000,
        group="Mass & payload",
    )
    gripper_mass: float = param(
        0.025, lo=0.005, hi=1.0, step=0.005, label="Gripper mass (w/o servo)", unit="g",
        scale=1000, group="Mass & payload",
    )
    payload_mass: float = param(
        0.050, lo=0.0, hi=3.0, step=0.005, label="Payload", unit="g", scale=1000,
        group="Mass & payload", help="Heaviest object the arm must lift.",
    )
    base_mass: float = param(
        0.35, lo=0.05, hi=5.0, step=0.05, label="Base mass", unit="g", scale=1000,
        group="Mass & payload", help="Base plate, electronics, ballast.",
    )

    max_joint_speed: float = param(
        90.0, lo=15.0, hi=360.0, step=5.0, label="Max joint speed", unit="°/s", group="Motion",
    )
    max_joint_accel: float = param(
        180.0, lo=30.0, hi=1440.0, step=10.0, label="Max joint acceleration", unit="°/s²",
        group="Motion",
    )
    safety_factor: float = param(
        1.5, lo=1.0, hi=3.0, step=0.1, label="Safety factor", unit="×", group="Motion",
        help="Torque margin applied on top of the calculated worst case.",
    )

    board: str = choice(
        "arduino-uno", label="Microcontroller", group="Electronics",
        options_from="microcontroller",
    )
    power_source: str = choice(
        "auto", label="Servo power", group="Electronics", options_from="power_source:arm",
    )


SURFACE_OPTIONS = [
    {"value": "hard_floor", "label": "Hard floor (tile, wood)"},
    {"value": "carpet", "label": "Carpet"},
    {"value": "gravel", "label": "Gravel / packed dirt"},
    {"value": "grass", "label": "Grass"},
]


class RoverDesign(BaseModel):
    """Differential-drive rover (2WD + caster or 4WD skid steer)."""

    model_config = ConfigDict(extra="forbid")

    template: Literal["rover"] = "rover"
    name: str = Field("My Rover", min_length=1, max_length=80)

    chassis_length: float = param(
        0.20, lo=0.08, hi=0.80, step=0.01, label="Chassis length", unit="mm", scale=1000,
        group="Geometry",
    )
    chassis_width: float = param(
        0.14, lo=0.06, hi=0.60, step=0.01, label="Chassis width", unit="mm", scale=1000,
        group="Geometry",
    )
    wheel_diameter: float = param(
        0.065, lo=0.03, hi=0.25, step=0.005, label="Wheel diameter", unit="mm", scale=1000,
        group="Geometry",
    )
    track_width: float = param(
        0.17, lo=0.08, hi=0.80, step=0.005, label="Track width", unit="mm", scale=1000,
        group="Geometry", help="Distance between the left and right wheel contact points.",
    )
    drive_motors: Literal[2, 4] = choice(
        2, label="Drivetrain", group="Geometry",
        options=[
            {"value": 2, "label": "2WD + caster"},
            {"value": 4, "label": "4WD skid-steer"},
        ],
    )

    chassis_mass: float = param(
        0.40, lo=0.05, hi=10.0, step=0.05, label="Chassis mass", unit="kg", group="Mass & payload",
        help="Frame, wheels and mounting hardware (motors and battery are added automatically).",
    )
    payload_mass: float = param(
        0.20, lo=0.0, hi=10.0, step=0.05, label="Payload", unit="kg", group="Mass & payload",
    )

    max_speed: float = param(
        0.5, lo=0.05, hi=3.0, step=0.05, label="Top speed", unit="m/s", group="Motion",
    )
    max_accel: float = param(
        0.5, lo=0.1, hi=5.0, step=0.1, label="Acceleration", unit="m/s²", group="Motion",
    )
    max_incline: float = param(
        10.0, lo=0.0, hi=30.0, step=1.0, label="Steepest slope", unit="°", group="Motion",
    )
    surface: Literal["hard_floor", "carpet", "gravel", "grass"] = choice(
        "hard_floor", label="Terrain", group="Motion", options=SURFACE_OPTIONS,
    )
    safety_factor: float = param(
        1.5, lo=1.0, hi=3.0, step=0.1, label="Safety factor", unit="×", group="Motion",
    )

    board: str = choice(
        "arduino-uno", label="Microcontroller", group="Electronics",
        options_from="microcontroller",
    )
    power_source: str = choice(
        "auto", label="Battery", group="Electronics", options_from="power_source:rover",
    )
    motor_driver: Literal["auto", "l298n", "tb6612fng", "mdd10a"] = choice(
        "auto", label="Motor driver", group="Electronics",
        options=[
            {"value": "auto", "label": "Auto (recommended)"},
            {"value": "l298n", "label": "L298N"},
            {"value": "tb6612fng", "label": "TB6612FNG"},
            {"value": "mdd10a", "label": "MDD10A (10 A)"},
        ],
    )
    obstacle_sensor: bool = toggle(
        True, label="HC-SR04 obstacle sensor", group="Electronics",
    )


Design = Annotated[ArmDesign | RoverDesign, Field(discriminator="template")]

TEMPLATE_MODELS: dict[str, type[BaseModel]] = {"arm": ArmDesign, "rover": RoverDesign}
