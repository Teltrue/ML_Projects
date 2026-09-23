"""3-axis arm template: DH model, analytic IK, worst-case torque sizing, stability, trajectories.

Joint layout (standard DH, angles in degrees at the API boundary):

====  =========  =====  ====  =====  ==============
 i    joint       d      a    alpha  limits (deg)
====  =========  =====  ====  =====  ==============
 1    base yaw    h      0    90°    -90 .. 90
 2    shoulder    0      L1   0      0 .. 180
 3    elbow       0      L2   0      -180 .. 0
====  =========  =====  ====  =====  ==============

``theta2`` is measured up from horizontal and ``theta3`` is the elbow bend relative to the
upper arm (0 = straight, negative = bent downward, i.e. "elbow up"). Each joint maps to a
0-180° hobby servo with ``servo = SERVO_OFFSET + SERVO_DIR * theta``.
"""

from dataclasses import dataclass

import numpy as np

from app.engines.mechanical.kinematics import (
    GRAVITY,
    Body,
    DHLink,
    center_of_mass,
    fk,
    forward_kinematics,
    rod_unit_inertia,
    unit_gravity_torque,
    unit_inertia_diagonal,
)
from app.schemas.design import ArmDesign

JOINT_NAMES = ("base", "shoulder", "elbow")
JOINT_LABELS = ("Base yaw", "Shoulder pitch", "Elbow pitch")
JOINT_LIMITS_DEG = ((-90.0, 90.0), (0.0, 180.0), (-180.0, 0.0))
HOME_DEG = (0.0, 90.0, -90.0)
SERVO_OFFSET_DEG = (90.0, 0.0, 180.0)
SERVO_DIR = (1.0, 1.0, 1.0)

SWEEP_STEP_DEG = 5.0
GRIP_FRICTION = 0.5  # rubber-padded fingers on a typical object
GRIP_LEVER_M = 0.025  # servo horn to finger contact
MIN_GRIP_TORQUE_NM = 0.03
LIMIT_TOL_DEG = 1e-6


@dataclass(frozen=True)
class ActuatorMasses:
    """Masses of the servos themselves, fed back from the Electrical Engine's selection."""

    base: float = 0.0
    shoulder: float = 0.0
    elbow: float = 0.0
    gripper: float = 0.0


# --------------------------------------------------------------------------- model


def dh_links(design: ArmDesign) -> list[DHLink]:
    return [
        DHLink(d=design.base_height, a=0.0, alpha=np.pi / 2),
        DHLink(d=0.0, a=design.upper_arm_length, alpha=0.0),
        DHLink(d=0.0, a=design.forearm_length, alpha=0.0),
    ]


def dh_table(design: ArmDesign) -> list[dict]:
    return [
        {"joint": i + 1, "name": JOINT_LABELS[i], "theta": f"θ{i + 1}", "d": link.d,
         "a": link.a, "alpha_deg": float(np.degrees(link.alpha)),
         "limits_deg": list(JOINT_LIMITS_DEG[i])}
        for i, link in enumerate(dh_links(design))
    ]


def moving_bodies(design: ArmDesign, act: ActuatorMasses,
                  payload: float | None = None) -> list[Body]:
    """Bodies carried by the joints, i.e. everything that loads a servo."""
    l1, l2 = design.upper_arm_length, design.forearm_length
    payload = design.payload_mass if payload is None else payload
    return [
        Body("upper_arm", design.upper_arm_mass, 2, np.array([-l1 / 2, 0.0, 0.0]),
             rod_unit_inertia(l1)),
        Body("elbow_servo", act.elbow, 2, np.zeros(3)),
        Body("forearm", design.forearm_mass, 3, np.array([-l2 / 2, 0.0, 0.0]),
             rod_unit_inertia(l2)),
        Body("gripper", design.gripper_mass + act.gripper, 3, np.zeros(3)),
        Body("payload", payload, 3, np.zeros(3)),
    ]


def all_bodies(design: ArmDesign, act: ActuatorMasses) -> list[Body]:
    """Every mass of the robot, for centre-of-mass and tip-over checks."""
    return [
        Body("base", design.base_mass, 0, np.array([0.0, 0.0, 0.01])),
        Body("base_servo", act.base, 0, np.array([0.0, 0.0, design.base_height * 0.3])),
        Body("shoulder_servo", act.shoulder, 1, np.zeros(3)),
        *moving_bodies(design, act),
    ]


# --------------------------------------------------------------------------- kinematics


def forward(design: ArmDesign, q_deg: tuple[float, float, float] | list[float]) -> dict:
    frames = fk(dh_links(design), np.radians(q_deg))
    points = [f[:3, 3] for f in frames]  # base, shoulder, elbow, end effector
    return {
        "joint_positions": [p.tolist() for p in points],
        "ee": points[-1].tolist(),
        "frames": frames,
    }


def within_limits(q_deg: np.ndarray) -> bool:
    return all(lo - LIMIT_TOL_DEG <= q <= hi + LIMIT_TOL_DEG
               for q, (lo, hi) in zip(q_deg, JOINT_LIMITS_DEG, strict=True))


def limit_violation(q_deg: np.ndarray) -> float:
    return float(sum(max(lo - q, 0.0, q - hi) for q, (lo, hi) in zip(q_deg, JOINT_LIMITS_DEG,
                                                                         strict=True)))


def clamp_to_limits(q_deg: np.ndarray) -> np.ndarray:
    return np.array([np.clip(q, lo, hi) for q, (lo, hi) in zip(q_deg, JOINT_LIMITS_DEG,
                                                                  strict=True)])


def wrap_deg(angle: float) -> float:
    """Wrap to (-180, 180]."""
    wrapped = (angle + 180.0) % 360.0 - 180.0
    return 180.0 if wrapped == -180.0 else wrapped


@dataclass(frozen=True)
class IKSolution:
    q_deg: tuple[float, float, float]
    reachable: bool
    within_limits: bool
    elbow: str
    message: str

    @property
    def exact(self) -> bool:
        return self.reachable and self.within_limits


def reach(design: ArmDesign) -> dict:
    l1, l2 = design.upper_arm_length, design.forearm_length
    return {"min": abs(l1 - l2), "max": l1 + l2, "shoulder_height": design.base_height}


def inverse(
    design: ArmDesign,
    target: tuple[float, float, float] | list[float],
    current_deg: tuple[float, float, float] | list[float] | None = None,
) -> IKSolution:
    """Closed-form IK. Unreachable targets are projected onto the workspace boundary so the
    arm still points at them; the result flags whether the solution is exact."""
    x, y, z = (float(v) for v in target)
    l1, l2 = design.upper_arm_length, design.forearm_length
    s = z - design.base_height
    r_xy = float(np.hypot(x, y))
    current = np.array(current_deg if current_deg is not None else HOME_DEG, dtype=float)

    if r_xy < 1e-9:
        yaw_options = [(float(current[0]), 0.0)]
    else:
        yaw = float(np.degrees(np.arctan2(y, x)))
        # Face the target, or face away and reach back over the top.
        yaw_options = [(yaw, r_xy), (wrap_deg(yaw + 180.0), -r_xy)]

    dist = float(np.hypot(r_xy, s))
    reach_min, reach_max = abs(l1 - l2), l1 + l2
    reachable = reach_min - 1e-9 <= dist <= reach_max + 1e-9

    candidates: list[tuple[np.ndarray, str]] = []
    for yaw, r in yaw_options:
        rr, ss = r, s
        if not reachable:
            if dist < 1e-9:
                rr, ss = reach_min, 0.0
            else:
                scale = float(np.clip(dist, reach_min, reach_max)) / dist
                rr, ss = r * scale, s * scale
        cos_elbow = (rr**2 + ss**2 - l1**2 - l2**2) / (2 * l1 * l2)
        cos_elbow = float(np.clip(cos_elbow, -1.0, 1.0))
        for elbow, sign in (("up", -1.0), ("down", 1.0)):
            t3 = sign * np.arccos(cos_elbow)
            t2 = np.arctan2(ss, rr) - np.arctan2(l2 * np.sin(t3), l1 + l2 * np.cos(t3))
            q = np.array([wrap_deg(yaw), wrap_deg(float(np.degrees(t2))),
                          wrap_deg(float(np.degrees(t3)))])
            # The folded elbow limit is -180 exactly; keep it on the valid side of the wrap.
            if q[2] == 180.0 and elbow == "up":
                q[2] = -180.0
            candidates.append((q, elbow))

    def rank(item: tuple[np.ndarray, str]) -> tuple:
        q, elbow = item
        return (limit_violation(q) > LIMIT_TOL_DEG, limit_violation(q), elbow != "up",
                float(np.abs(q - current).sum()))

    q, elbow = min(candidates, key=rank)
    ok_limits = within_limits(q)
    q = clamp_to_limits(q)

    if not reachable:
        gap = (dist - reach_max) if dist > reach_max else (reach_min - dist)
        side = "beyond the maximum reach" if dist > reach_max else "too close to the shoulder"
        message = f"Target is {gap * 1000:.0f} mm {side}; arm points at it instead."
    elif not ok_limits:
        message = ("Target is inside the reach sphere but needs joint angles outside the "
                   "servo range.")
    else:
        message = "Target reached."
    return IKSolution(tuple(float(v) for v in q), reachable, ok_limits, elbow, message)


def servo_angles(q_deg: tuple[float, float, float] | list[float]) -> list[float]:
    return [float(o + d * q) for o, d, q in zip(SERVO_OFFSET_DEG, SERVO_DIR, q_deg, strict=True)]


# --------------------------------------------------------------------------- statics / dynamics


def _sweep_poses() -> np.ndarray:
    """Shoulder/elbow grid covering the full joint range. Gravity and inertia about every
    joint are independent of the base yaw, so theta1 is fixed at 0."""
    t2 = np.arange(JOINT_LIMITS_DEG[1][0], JOINT_LIMITS_DEG[1][1] + 1e-9, SWEEP_STEP_DEG)
    t3 = np.arange(JOINT_LIMITS_DEG[2][0], JOINT_LIMITS_DEG[2][1] + 1e-9, SWEEP_STEP_DEG)
    g2, g3 = np.meshgrid(t2, t3, indexing="ij")
    return np.column_stack([np.zeros(g2.size), g2.ravel(), g3.ravel()])


@dataclass(frozen=True)
class LoadCoefficients:
    """Per-body torque coefficients over the pose grid. Torques are linear in body masses, so
    re-sizing after a servo swap is a cheap weighted sum instead of a new sweep."""

    poses_deg: np.ndarray  # (P, 3)
    names: tuple[str, ...]
    gravity: np.ndarray  # (B, P, 3) N·m per kg
    inertia: np.ndarray  # (B, P, 3) kg·m² per kg (diagonal of M(q))


def load_coefficients(design: ArmDesign) -> LoadCoefficients:
    poses = _sweep_poses()
    frames = forward_kinematics(dh_links(design), np.radians(poses))
    bodies = moving_bodies(design, ActuatorMasses())
    return LoadCoefficients(
        poses_deg=poses,
        names=tuple(b.name for b in bodies),
        gravity=np.stack([unit_gravity_torque(frames, b) for b in bodies]),
        inertia=np.stack([unit_inertia_diagonal(frames, b) for b in bodies]),
    )


def _mass_vector(design: ArmDesign, act: ActuatorMasses, coeffs: LoadCoefficients,
                 payload: float | None = None) -> np.ndarray:
    by_name = {b.name: b.mass for b in moving_bodies(design, act, payload)}
    return np.array([by_name[n] for n in coeffs.names])


@dataclass(frozen=True)
class JointLoad:
    name: str
    label: str
    gravity_nm: float
    inertial_nm: float
    required_nm: float  # (gravity + inertial) * safety factor at the worst pose
    worst_pose_deg: tuple[float, float, float]


def joint_loads(design: ArmDesign, act: ActuatorMasses,
                coeffs: LoadCoefficients | None = None) -> list[JointLoad]:
    coeffs = coeffs or load_coefficients(design)
    m = _mass_vector(design, act, coeffs)
    alpha = np.radians(design.max_joint_accel)
    gravity = np.abs(np.einsum("b,bpj->pj", m, coeffs.gravity))
    inertial = np.einsum("b,bpj->pj", m, coeffs.inertia) * alpha
    total = gravity + inertial
    worst = np.argmax(total, axis=0)
    loads = []
    for j, idx in enumerate(worst):
        loads.append(JointLoad(
            name=JOINT_NAMES[j],
            label=JOINT_LABELS[j],
            gravity_nm=float(gravity[idx, j]),
            inertial_nm=float(inertial[idx, j]),
            required_nm=float(total[idx, j] * design.safety_factor),
            worst_pose_deg=tuple(float(v) for v in coeffs.poses_deg[idx]),
        ))
    return loads


def gripper_torque(design: ArmDesign) -> float:
    """Servo torque needed to squeeze the payload hard enough that friction holds it."""
    grip_force = design.payload_mass * GRAVITY / (2 * GRIP_FRICTION)
    return max(grip_force * GRIP_LEVER_M * design.safety_factor, MIN_GRIP_TORQUE_NM)


def max_payload(design: ArmDesign, act: ActuatorMasses, available_nm: list[float],
                coeffs: LoadCoefficients | None = None) -> float:
    """Largest payload the selected joint servos can handle with the chosen safety factor."""
    coeffs = coeffs or load_coefficients(design)
    alpha = np.radians(design.max_joint_accel)
    m = _mass_vector(design, act, coeffs, payload=0.0)
    p = coeffs.names.index("payload")
    base_g = np.abs(np.einsum("b,bpj->pj", m, coeffs.gravity))
    base_i = np.einsum("b,bpj->pj", m, coeffs.inertia) * alpha
    per_kg = np.abs(coeffs.gravity[p]) + coeffs.inertia[p] * alpha
    limit = np.array(available_nm) / design.safety_factor
    headroom = limit - base_g - base_i
    with np.errstate(divide="ignore", invalid="ignore"):
        allowed = np.where(per_kg > 1e-12, headroom / per_kg, np.inf)
    # A joint with no headroom even when empty supports no payload at all.
    allowed = np.where(headroom < 0, 0.0, allowed)
    return float(max(np.min(allowed), 0.0))


def holding_torques(design: ArmDesign, act: ActuatorMasses, q_deg: list[float]) -> list[float]:
    frames = forward_kinematics(dh_links(design), np.radians(q_deg)[None, :])
    tau = np.zeros(3)
    for body in moving_bodies(design, act):
        tau += body.mass * unit_gravity_torque(frames, body)[0]
    return [float(abs(t)) for t in tau]


def stability(design: ArmDesign, act: ActuatorMasses, q_deg: list[float]) -> dict:
    """Tip-over check: the combined centre of mass must stay above the base footprint."""
    frames = forward_kinematics(dh_links(design), np.radians(q_deg)[None, :])
    com, total = center_of_mass(frames, all_bodies(design, act))
    com = com[0]
    offset = float(np.hypot(com[0], com[1]))
    radius = design.base_radius
    # Ballast at the base axis needed to pull the COM back inside the footprint.
    ballast = max(0.0, total * offset / radius - total) if radius > 0 else 0.0
    return {
        "pose_deg": [float(v) for v in q_deg],
        "com": com.tolist(),
        "total_mass_kg": total,
        "horizontal_offset_m": offset,
        "base_radius_m": radius,
        "stable": offset <= radius,
        "ballast_kg": ballast,
    }


# --------------------------------------------------------------------------- trajectories


@dataclass(frozen=True)
class Waypoint:
    label: str
    gripper: float  # 0 = open, 1 = closed
    position: tuple[float, float, float] | None = None
    joints_deg: tuple[float, float, float] | None = None


def demo_waypoints(design: ArmDesign) -> list[Waypoint]:
    """A pick-and-place routine scaled to the arm's reach."""
    rch = reach(design)
    rho = rch["min"] + 0.7 * (rch["max"] - rch["min"])
    z_pick = max(0.02, design.base_height - 0.6 * rho)
    dz = z_pick - design.base_height
    r = float(np.sqrt(max(rho**2 - dz**2, (0.3 * rho) ** 2)))
    lift = 0.3 * rho

    def at(yaw_deg: float, z: float) -> tuple[float, float, float]:
        yaw = np.radians(yaw_deg)
        return (float(r * np.cos(yaw)), float(r * np.sin(yaw)), float(z))

    pick, place = -50.0, 50.0
    return [
        Waypoint("home", 0.0, joints_deg=HOME_DEG),
        Waypoint("above pick", 0.0, position=at(pick, z_pick + lift)),
        Waypoint("pick", 0.0, position=at(pick, z_pick)),
        Waypoint("grip", 1.0, position=at(pick, z_pick)),
        Waypoint("lift", 1.0, position=at(pick, z_pick + lift)),
        Waypoint("above place", 1.0, position=at(place, z_pick + lift)),
        Waypoint("place", 1.0, position=at(place, z_pick)),
        Waypoint("release", 0.0, position=at(place, z_pick)),
        Waypoint("retreat", 0.0, position=at(place, z_pick + lift)),
        Waypoint("home", 0.0, joints_deg=HOME_DEG),
    ]


def _segment_duration(delta_deg: float, v_max: float, a_max: float) -> float:
    """Shortest quintic (rest-to-rest) move that respects the speed and acceleration limits."""
    if delta_deg < 1e-9:
        return 0.0
    t_v = 15.0 / 8.0 * delta_deg / v_max
    t_a = np.sqrt(10.0 / np.sqrt(3.0) * delta_deg / a_max)
    return float(max(t_v, t_a))


def plan_trajectory(design: ArmDesign, waypoints: list[Waypoint], fps: float = 30.0) -> dict:
    resolved = []
    current = np.array(HOME_DEG)
    for wp in waypoints:
        if wp.joints_deg is not None:
            q = np.array(wp.joints_deg, dtype=float)
            sol = None
        else:
            sol = inverse(design, wp.position, current)
            q = np.array(sol.q_deg)
        resolved.append({
            "label": wp.label,
            "gripper": wp.gripper,
            "position": list(wp.position) if wp.position else forward(design, q)["ee"],
            "q_deg": q.tolist(),
            "reachable": sol.exact if sol else True,
        })
        current = q

    def sample(t: float, q: np.ndarray | list[float], gripper: float) -> dict:
        q = [float(v) for v in q]
        return {"t": round(t, 4), "q": q, "gripper": gripper, "ee": forward(design, q)["ee"]}

    samples = [sample(0.0, resolved[0]["q_deg"], resolved[0]["gripper"])]
    t0 = 0.0
    for prev, nxt in zip(resolved, resolved[1:], strict=False):
        qa, qb = np.array(prev["q_deg"]), np.array(nxt["q_deg"])
        duration = _segment_duration(float(np.max(np.abs(qb - qa))), design.max_joint_speed,
                                     design.max_joint_accel)
        if prev["gripper"] != nxt["gripper"]:
            duration = max(duration, 0.5)
        duration = max(duration, 0.2)
        steps = max(int(np.ceil(duration * fps)), 1)
        for k in range(1, steps + 1):
            tau = k / steps
            s = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
            samples.append(sample(t0 + tau * duration, qa + (qb - qa) * s,
                                  prev["gripper"] + (nxt["gripper"] - prev["gripper"]) * s))
        nxt["t"] = round(t0 + duration, 4)
        t0 += duration
    resolved[0]["t"] = 0.0
    return {"duration": t0, "waypoints": resolved, "samples": samples}
