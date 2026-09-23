import numpy as np
import pytest

from app.engines.mechanical import arm
from app.schemas.design import ArmDesign

DESIGN = ArmDesign()
SERVOS = arm.ActuatorMasses(base=0.009, shoulder=0.055, elbow=0.055, gripper=0.009)


def test_forward_kinematics_known_poses():
    assert arm.forward(DESIGN, (0, 0, 0))["ee"] == pytest.approx([0.24, 0.0, 0.10])
    assert arm.forward(DESIGN, (90, 90, -90))["ee"] == pytest.approx([0.0, 0.12, 0.22])


def test_ik_round_trip_for_reachable_targets():
    rng = np.random.default_rng(1)
    solved = 0
    for _ in range(300):
        q = [rng.uniform(lo, hi) for lo, hi in arm.JOINT_LIMITS_DEG]
        target = arm.forward(DESIGN, q)["ee"]
        sol = arm.inverse(DESIGN, target)
        assert sol.exact, (q, sol)
        assert arm.forward(DESIGN, sol.q_deg)["ee"] == pytest.approx(target, abs=1e-6)
        assert arm.within_limits(np.array(sol.q_deg))
        solved += 1
    assert solved == 300


def test_ik_prefers_elbow_up_and_facing_the_target():
    sol = arm.inverse(DESIGN, (0.15, 0.05, 0.12))
    assert sol.exact and sol.elbow == "up"
    assert sol.q_deg[0] == pytest.approx(np.degrees(np.arctan2(0.05, 0.15)))
    assert sol.q_deg[2] < 0


def test_ik_reaches_behind_by_going_over_the_top():
    target = arm.forward(DESIGN, (0.0, 150.0, -30.0))["ee"]
    assert target[0] < 0  # behind the base; facing it would need a yaw of 180 degrees
    sol = arm.inverse(DESIGN, target)
    assert sol.exact
    assert sol.q_deg == pytest.approx((0.0, 150.0, -30.0), abs=1e-6)


def test_ik_flags_targets_outside_the_servo_range():
    sol = arm.inverse(DESIGN, (-0.15, 0.0, 0.2))  # would need the elbow to bend upward
    assert sol.reachable and not sol.within_limits
    assert arm.within_limits(np.array(sol.q_deg))  # the returned pose is still safe


def test_ik_projects_unreachable_targets_onto_the_workspace():
    sol = arm.inverse(DESIGN, (0.5, 0.0, 0.1))
    assert not sol.reachable
    assert "beyond the maximum reach" in sol.message
    ee = arm.forward(DESIGN, sol.q_deg)["ee"]
    assert ee == pytest.approx([0.24, 0.0, 0.1], abs=1e-6)  # fully stretched towards it


def test_worst_case_torques_match_hand_calculation():
    loads = {ld.name: ld for ld in arm.joint_loads(DESIGN, SERVOS)}
    g = 9.81
    l1 = l2 = 0.12
    tip = DESIGN.gripper_mass + SERVOS.gripper + DESIGN.payload_mass
    shoulder = g * (DESIGN.upper_arm_mass * l1 / 2 + SERVOS.elbow * l1
                    + DESIGN.forearm_mass * (l1 + l2 / 2) + tip * (l1 + l2))
    elbow = g * (DESIGN.forearm_mass * l2 / 2 + tip * l2)
    assert loads["shoulder"].gravity_nm == pytest.approx(shoulder)
    assert loads["shoulder"].worst_pose_deg == (0.0, 0.0, 0.0)
    assert loads["elbow"].gravity_nm == pytest.approx(elbow)
    assert loads["base"].gravity_nm == pytest.approx(0.0)
    for ld in loads.values():
        expected = (ld.gravity_nm + ld.inertial_nm) * DESIGN.safety_factor
        assert ld.required_nm == pytest.approx(expected)


def test_heavier_payload_needs_more_torque():
    light = arm.joint_loads(DESIGN, SERVOS)
    heavy = arm.joint_loads(DESIGN.model_copy(update={"payload_mass": 0.5}), SERVOS)
    assert all(h.required_nm > lt.required_nm for h, lt in zip(heavy[1:], light[1:],
                                                                   strict=True))


def test_max_payload_saturates_the_limiting_joint():
    available = [0.5, 1.0, 0.6]
    limit = arm.max_payload(DESIGN, SERVOS, available)
    at_limit = DESIGN.model_copy(update={"payload_mass": limit})
    loads = arm.joint_loads(at_limit, SERVOS)
    utilisation = [ld.required_nm / a for ld, a in zip(loads, available, strict=True)]
    assert max(utilisation) == pytest.approx(1.0, rel=1e-6)


def test_stability_detects_tip_over_and_ballast_fixes_it():
    design = DESIGN.model_copy(update={"payload_mass": 1.0, "base_mass": 0.1})
    result = arm.stability(design, SERVOS, [0.0, 0.0, 0.0])
    assert not result["stable"]
    ballasted = design.model_copy(update={"base_mass": design.base_mass
                                          + result["ballast_kg"] + 1e-6})
    assert arm.stability(ballasted, SERVOS, [0.0, 0.0, 0.0])["stable"]


def test_demo_trajectory_is_reachable_and_respects_speed_limit():
    plan = arm.plan_trajectory(DESIGN, arm.demo_waypoints(DESIGN))
    assert all(w["reachable"] for w in plan["waypoints"])
    samples = plan["samples"]
    assert samples[0]["q"] == pytest.approx(list(arm.HOME_DEG))
    assert samples[-1]["q"] == pytest.approx(list(arm.HOME_DEG))
    for a, b in zip(samples, samples[1:], strict=False):
        dt = b["t"] - a["t"]
        if dt > 0:
            speed = max(abs(x - y) for x, y in zip(a["q"], b["q"], strict=True)) / dt
            assert speed <= DESIGN.max_joint_speed * 1.05


@pytest.mark.parametrize("upper,fore,height", [(0.05, 0.40, 0.04), (0.40, 0.05, 0.40),
                                               (0.2, 0.2, 0.3)])
def test_demo_waypoints_adapt_to_extreme_geometry(upper, fore, height):
    design = ArmDesign(upper_arm_length=upper, forearm_length=fore, base_height=height)
    plan = arm.plan_trajectory(design, arm.demo_waypoints(design))
    for sample in plan["samples"]:
        assert arm.within_limits(np.array(sample["q"]))
