"""Request and response models for the HTTP API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.design import ArmDesign, Design, RoverDesign

Vec3 = tuple[float, float, float]


# --------------------------------------------------------------------------- shared pieces


class CheckOut(BaseModel):
    id: str
    severity: Literal["pass", "info", "warning", "error"]
    title: str
    detail: str
    fix: str | None = None
    auto_fixed: bool = False
    engine: Literal["mechanical", "electrical"] = "electrical"


class PartOut(BaseModel):
    ref: str
    component_id: str
    name: str
    label: str
    category: str
    column: int
    pins: list[str]
    auto_added: bool
    in_diagram: bool
    reason: str


class WireOut(BaseModel):
    a: str
    a_pin: str
    b: str
    b_pin: str
    net: str
    kind: Literal["power", "ground", "signal", "motor"]


class BomItemOut(BaseModel):
    component_id: str
    name: str
    category: str
    qty: int
    unit_price_usd: float
    total_usd: float
    refs: list[str]
    reason: str
    note: str | None = None
    auto_added: bool


class RailOut(BaseModel):
    name: str
    voltage: float
    source: str
    typical_a: float
    peak_a: float
    capacity_a: float
    status: Literal["ok", "warning", "error"]


class AlternativeOut(BaseModel):
    component_id: str
    name: str
    price_usd: float
    rating: str


class ActuatorOut(BaseModel):
    role: str
    label: str
    component_id: str
    name: str
    required_nm: float
    required_kgcm: float
    available_nm: float
    available_kgcm: float
    utilization: float
    status: Literal["ok", "marginal", "insufficient"]
    rationale: str
    alternatives: list[AlternativeOut]
    mass_kg: float
    price_usd: float
    extra: dict[str, Any] = {}


class BoardOut(BaseModel):
    id: str
    name: str
    logic_v: float
    languages: list[str]


class ElectricalOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    board: BoardOut
    actuators: list[ActuatorOut]
    parts: list[PartOut]
    wires: list[WireOut]
    bom: list[BomItemOut]
    rails: list[RailOut]
    checks: list[CheckOut]
    pin_map: dict[str, int]
    pin_labels: dict[str, str]
    total_cost_usd: float
    power_source_id: str


class SummaryOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["ok", "warning", "error"]
    headline: str
    total_cost_usd: float
    total_mass_kg: float
    check_counts: dict[str, int]
    auto_fixes: int


class AnalysisOut(BaseModel):
    template: Literal["arm", "rover"]
    name: str
    mechanical: dict[str, Any] = Field(description="Template-specific mechanical results")
    electrical: ElectricalOut
    summary: SummaryOut


# --------------------------------------------------------------------------- requests


class AnalyzeRequest(BaseModel):
    design: Design


class CodegenRequest(BaseModel):
    design: Design
    language: Literal["arduino", "micropython"] = "arduino"
    preset: Literal["square", "figure8", "spin"] = "square"


class CodegenOut(BaseModel):
    language: str
    language_label: str
    filename: str
    board: str
    code: str
    libraries: list[str]
    instructions: list[str]
    warnings: list[str]


class ArmPoseRequest(BaseModel):
    design: ArmDesign
    mode: Literal["ik", "fk"] = "ik"
    target: Vec3 | None = Field(None, description="Gripper target in metres (IK mode)")
    joints: Vec3 | None = Field(None, description="Joint angles in degrees (FK mode)")
    current: Vec3 | None = Field(None, description="Current joints, to keep IK continuous")
    actuator_masses_kg: dict[str, float] | None = None


class ArmPoseOut(BaseModel):
    q_deg: list[float]
    servo_deg: list[float]
    ee: list[float]
    joint_positions: list[list[float]]
    reachable: bool
    within_limits: bool
    exact: bool
    message: str
    holding_torque_nm: list[float]
    com: list[float]
    stable: bool
    warnings: list[str]


class WaypointIn(BaseModel):
    label: str = Field("", max_length=40)
    gripper: float = Field(0.0, ge=0.0, le=1.0)
    position: Vec3 | None = None
    joints: Vec3 | None = None

    @model_validator(mode="after")
    def _one_target(self) -> "WaypointIn":
        if (self.position is None) == (self.joints is None):
            raise ValueError("Give each waypoint either a position or joint angles")
        return self


class ArmTrajectoryRequest(BaseModel):
    design: ArmDesign
    waypoints: list[WaypointIn] | None = Field(
        None, max_length=50, description="Omit to get the pick-and-place demo for this arm."
    )


class RoverStepIn(BaseModel):
    label: str = Field("", max_length=40)
    left: float = Field(..., ge=-5, le=5, description="Left wheel speed, m/s")
    right: float = Field(..., ge=-5, le=5, description="Right wheel speed, m/s")
    duration: float = Field(..., gt=0, le=120, description="Seconds")


class RoverSimRequest(BaseModel):
    design: RoverDesign
    preset: Literal["square", "figure8", "spin"] = "square"
    steps: list[RoverStepIn] | None = Field(
        None, max_length=60, description="Overrides the preset (at most 10 minutes in total)"
    )

    @model_validator(mode="after")
    def _bounded(self) -> "RoverSimRequest":
        if self.steps and sum(s.duration for s in self.steps) > 600:
            raise ValueError("A simulation can last at most 600 s")
        return self


# --------------------------------------------------------------------------- catalog & projects


class ComponentOut(BaseModel):
    id: str
    category: str
    name: str
    description: str
    price_usd: float
    mass_kg: float
    specs: dict[str, Any]


class ParameterOut(BaseModel):
    key: str
    kind: Literal["slider", "select", "toggle"]
    label: str
    group: str
    help: str = ""
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    scale: float = 1.0
    options: list[dict[str, Any]] = []


class TemplateOut(BaseModel):
    id: Literal["arm", "rover"]
    name: str
    tagline: str
    description: str
    defaults: dict[str, Any]
    groups: list[str]
    parameters: list[ParameterOut]


class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    design: Design


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    template: str
    design: dict[str, Any]
    created_at: datetime
    updated_at: datetime
