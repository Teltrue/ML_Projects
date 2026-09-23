"""Differential-drive rover template: drive-force budget, wheel sizing and motion simulation."""

from dataclasses import dataclass

import numpy as np

from app.engines.mechanical.kinematics import GRAVITY
from app.schemas.design import RoverDesign

# (rolling-resistance coefficient, rubber-on-surface static friction)
SURFACES: dict[str, tuple[float, float]] = {
    "hard_floor": (0.015, 0.80),
    "carpet": (0.050, 0.65),
    "gravel": (0.080, 0.55),
    "grass": (0.100, 0.45),
}
# Share of the weight on the driven wheels (the caster carries the rest on a 2WD rover).
DRIVEN_WEIGHT_SHARE = {2: 0.8, 4: 1.0}
ELECTRONICS_MASS = 0.08  # board, driver, wiring, sensor mounts


@dataclass(frozen=True)
class RoverLoads:
    total_mass: float
    rolling_n: float
    grade_n: float
    accel_n: float
    total_n: float
    wheel_rpm: float
    torque_per_motor_nm: float  # includes the safety factor
    load_torque_per_motor_nm: float  # without safety factor, worst case (accel on slope)
    cruise_torque_per_motor_nm: float  # flat ground, constant top speed
    power_per_motor_w: float
    traction_required_n: float
    traction_available_n: float

    @property
    def slips(self) -> bool:
        return self.traction_required_n > self.traction_available_n


def loads(design: RoverDesign, total_mass: float) -> RoverLoads:
    crr, mu = SURFACES[design.surface]
    slope = np.radians(design.max_incline)
    weight = total_mass * GRAVITY
    rolling = crr * weight * np.cos(slope)
    grade = weight * np.sin(slope)
    accel = total_mass * design.max_accel
    total = rolling + grade + accel
    r = design.wheel_diameter / 2
    n = design.drive_motors
    load_torque = total * r / n
    wheel_rpm = design.max_speed / (np.pi * design.wheel_diameter) * 60.0
    omega = design.max_speed / r
    return RoverLoads(
        total_mass=total_mass,
        rolling_n=float(rolling),
        grade_n=float(grade),
        accel_n=float(accel),
        total_n=float(total),
        wheel_rpm=float(wheel_rpm),
        torque_per_motor_nm=float(load_torque * design.safety_factor),
        load_torque_per_motor_nm=float(load_torque),
        cruise_torque_per_motor_nm=float(crr * weight * r / n),
        power_per_motor_w=float(load_torque * design.safety_factor * omega),
        traction_required_n=float(total),
        traction_available_n=float(mu * weight * np.cos(slope) * DRIVEN_WEIGHT_SHARE[n]),
    )


def kinematics(design: RoverDesign) -> dict:
    """Differential-drive kinematics: v = (vR + vL) / 2, omega = (vR - vL) / W."""
    w = design.track_width
    yaw_rate = 2 * design.max_speed / w
    return {
        "max_yaw_rate_dps": float(np.degrees(yaw_rate)),
        "spin_360_s": float(2 * np.pi / yaw_rate),
        "stopping_distance_m": float(design.max_speed**2 / (2 * design.max_accel)),
        "time_to_top_speed_s": float(design.max_speed / design.max_accel),
        "wheel_circumference_m": float(np.pi * design.wheel_diameter),
        "min_turn_radius_m": 0.0,
    }


# --------------------------------------------------------------------------- simulation


@dataclass(frozen=True)
class DriveStep:
    label: str
    left: float  # wheel surface speed, m/s
    right: float
    duration: float  # s


PRESETS = {
    "square": "Drive a square, turning in place at each corner",
    "figure8": "Trace a figure-eight with gentle differential turns",
    "spin": "Spin a full turn in place each way",
}


def preset_program(design: RoverDesign, preset: str) -> list[DriveStep]:
    """Rest-to-rest manoeuvres. A stop step after every move lets each wheel ramp down, which
    makes the travelled distance exactly ``speed x duration`` (the ramps cancel out)."""
    v = 0.6 * design.max_speed
    v_turn = 0.4 * design.max_speed
    w = design.track_width
    stop = DriveStep("stop", 0.0, 0.0, v / design.max_accel + 0.15)
    steps: list[DriveStep] = []

    if preset == "square":
        side = float(np.clip(6 * design.chassis_length, 0.6, 2.5))
        turn_time = (np.pi / 2) * (w / 2) / v_turn
        for i in range(4):
            steps += [DriveStep(f"side {i + 1}", v, v, side / v), stop,
                      DriveStep(f"turn {i + 1}", -v_turn, v_turn, float(turn_time)), stop]
    elif preset == "figure8":
        radius = max(2.0 * w, 0.35)
        k = w / (2 * radius)
        lap = 2 * np.pi * radius / v
        steps += [DriveStep("left loop", v * (1 - k), v * (1 + k), float(lap)), stop,
                  DriveStep("right loop", v * (1 + k), v * (1 - k), float(lap)), stop]
    elif preset == "spin":
        spin_time = 2 * np.pi * (w / 2) / v_turn
        steps += [DriveStep("spin left", -v_turn, v_turn, float(spin_time)), stop,
                  DriveStep("spin right", v_turn, -v_turn, float(spin_time)), stop]
    else:
        raise ValueError(f"Unknown preset '{preset}'")
    return steps


def simulate(design: RoverDesign, steps: list[DriveStep], fps: float = 30.0,
             dt: float = 1 / 120) -> dict:
    """Integrate the unicycle model with acceleration-limited wheel speeds.

    Both wheels ramp together over the time the larger speed change needs, so the path
    curvature stays constant while accelerating (what the generated firmware does too).
    """
    r = design.wheel_diameter / 2
    w = design.track_width
    x = y = heading = 0.0
    vl = vr = 0.0
    ang_l = ang_r = 0.0
    t = 0.0
    next_sample = 0.0
    samples = []
    distance = 0.0

    def record() -> None:
        samples.append({
            "t": round(t, 4), "x": x, "y": y, "heading": heading,
            "wheel_left": ang_l, "wheel_right": ang_r,
            "v": (vl + vr) / 2, "omega": (vr - vl) / w,
        })

    record()
    next_sample += 1 / fps
    for step in steps:
        start_l, start_r = vl, vr
        d_l, d_r = step.left - start_l, step.right - start_r
        ramp = max(abs(d_l), abs(d_r)) / design.max_accel
        elapsed = 0.0
        while elapsed < step.duration - 1e-12:
            h = min(dt, step.duration - elapsed)
            # Split the sub-step at the end of the ramp so the speed profile stays exact.
            if elapsed < ramp < elapsed + h:
                h = ramp - elapsed
            elapsed += h
            frac = 1.0 if ramp == 0 else min(elapsed / ramp, 1.0)
            new_l, new_r = start_l + d_l * frac, start_r + d_r * frac
            avg_l, avg_r = (vl + new_l) / 2, (vr + new_r) / 2
            v, omega = (avg_l + avg_r) / 2, (avg_r - avg_l) / w
            if abs(omega) < 1e-9:
                x += v * float(np.cos(heading)) * h
                y += v * float(np.sin(heading)) * h
            else:
                x += v / omega * float(np.sin(heading + omega * h) - np.sin(heading))
                y -= v / omega * float(np.cos(heading + omega * h) - np.cos(heading))
            heading += omega * h
            ang_l += avg_l * h / r
            ang_r += avg_r * h / r
            distance += abs(v) * h
            vl, vr = new_l, new_r
            t += h
            if t + 1e-9 >= next_sample:
                record()
                next_sample += 1 / fps
    if samples[-1]["t"] != round(t, 4):
        record()
    xs = [s["x"] for s in samples]
    ys = [s["y"] for s in samples]
    return {
        "duration": t,
        "distance_m": distance,
        "bounds": {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys)},
        "steps": [s.__dict__ for s in steps],
        "samples": samples,
    }
