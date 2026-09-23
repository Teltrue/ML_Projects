"""The engines: analysis, kinematics, simulation and code generation."""

from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends

from app.catalog import Catalog
from app.deps import get_catalog
from app.engines.codegen.generator import generate
from app.engines.mechanical import arm, rover
from app.pipeline import analyze
from app.schemas.api import (
    AnalysisOut,
    AnalyzeRequest,
    ArmPoseOut,
    ArmPoseRequest,
    ArmTrajectoryRequest,
    CodegenOut,
    CodegenRequest,
    RoverSimRequest,
)

router = APIRouter(prefix="/api", tags=["engines"])
CatalogDep = Annotated[Catalog, Depends(get_catalog)]


@router.post("/analyze", response_model=AnalysisOut)
def analyze_design(req: AnalyzeRequest, catalog: CatalogDep) -> dict:
    """Run the Mechanical and Electrical engines on a design."""
    return analyze(req.design, catalog)


@router.post("/codegen", response_model=CodegenOut)
def generate_code(req: CodegenRequest, catalog: CatalogDep) -> dict:
    """Generate ready-to-flash firmware for a design."""
    return generate(req.design, catalog, req.language, req.preset)


@router.post("/arm/pose", response_model=ArmPoseOut)
def arm_pose(req: ArmPoseRequest) -> dict:
    """Forward or inverse kinematics for one pose, with holding torques and stability."""
    design = req.design
    if req.mode == "fk":
        requested = np.array(req.joints or arm.HOME_DEG, dtype=float)
        q = [float(v) for v in arm.clamp_to_limits(requested)]
        reachable = True
        within = arm.within_limits(requested)
        message = ("Joint angles set." if within
                   else "Some joint angles were outside the servo range and were clamped.")
    else:
        target = req.target or arm.forward(design, arm.HOME_DEG)["ee"]
        sol = arm.inverse(design, target, req.current)
        q, reachable, within, message = list(sol.q_deg), sol.reachable, sol.within_limits, \
            sol.message
    known = arm.ActuatorMasses.__dataclass_fields__
    masses = arm.ActuatorMasses(**{k: v for k, v in (req.actuator_masses_kg or {}).items()
                                   if k in known})
    fk = arm.forward(design, q)
    stab = arm.stability(design, masses, q)
    warnings = []
    if min(p[2] for p in fk["joint_positions"][2:]) < -1e-3:
        warnings.append("The arm would hit the table in this pose.")
    if not stab["stable"]:
        warnings.append("The arm would tip over in this pose - clamp or ballast the base.")
    return {
        "q_deg": q,
        "servo_deg": arm.servo_angles(q),
        "ee": fk["ee"],
        "joint_positions": fk["joint_positions"],
        "reachable": reachable,
        "within_limits": within,
        "exact": reachable and within,
        "message": message,
        "holding_torque_nm": arm.holding_torques(design, masses, q),
        "com": stab["com"],
        "stable": stab["stable"],
        "warnings": warnings,
    }


@router.post("/arm/trajectory")
def arm_trajectory(req: ArmTrajectoryRequest) -> dict:
    """Plan a smooth, speed/acceleration-limited joint trajectory through waypoints."""
    if req.waypoints:
        waypoints = [arm.Waypoint(w.label, w.gripper, w.position, w.joints)
                     for w in req.waypoints]
        if waypoints[0].position is not None:  # always start from home
            waypoints.insert(0, arm.Waypoint("home", waypoints[0].gripper,
                                             joints_deg=arm.HOME_DEG))
    else:
        waypoints = arm.demo_waypoints(req.design)
    return arm.plan_trajectory(req.design, waypoints)


@router.post("/rover/simulate")
def rover_simulate(req: RoverSimRequest) -> dict:
    """Simulate the rover driving a demo program (or custom wheel-speed steps)."""
    if req.steps:
        steps = [rover.DriveStep(s.label, s.left, s.right, s.duration) for s in req.steps]
    else:
        steps = rover.preset_program(req.design, req.preset)
    result = rover.simulate(req.design, steps)
    result["preset"] = None if req.steps else req.preset
    return result
