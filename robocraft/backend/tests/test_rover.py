import numpy as np
import pytest

from app.engines.mechanical import rover
from app.schemas.design import RoverDesign

DESIGN = RoverDesign()


def test_drive_force_budget_by_hand():
    m = 1.0
    loads = rover.loads(DESIGN, m)
    slope = np.radians(DESIGN.max_incline)
    crr, _ = rover.SURFACES[DESIGN.surface]
    expected = m * 9.81 * (crr * np.cos(slope) + np.sin(slope)) + m * DESIGN.max_accel
    assert loads.total_n == pytest.approx(expected)
    r = DESIGN.wheel_diameter / 2
    assert loads.torque_per_motor_nm == pytest.approx(expected * r / 2 * DESIGN.safety_factor)
    assert loads.wheel_rpm == pytest.approx(DESIGN.max_speed / (np.pi * DESIGN.wheel_diameter)
                                            * 60)


def test_four_wheel_drive_halves_per_motor_torque():
    two = rover.loads(DESIGN, 1.0)
    four = rover.loads(DESIGN.model_copy(update={"drive_motors": 4}), 1.0)
    assert four.torque_per_motor_nm == pytest.approx(two.torque_per_motor_nm / 2)


def test_traction_limit_on_steep_grass():
    design = DESIGN.model_copy(update={"surface": "grass", "max_incline": 30, "max_accel": 3})
    assert rover.loads(design, 1.0).slips


def test_differential_drive_kinematics():
    kin = rover.kinematics(DESIGN)
    assert kin["max_yaw_rate_dps"] == pytest.approx(np.degrees(2 * 0.5 / 0.17))
    assert kin["stopping_distance_m"] == pytest.approx(0.25)


@pytest.mark.parametrize("preset", list(rover.PRESETS))
def test_preset_paths_close_on_themselves(preset):
    result = rover.simulate(DESIGN, rover.preset_program(DESIGN, preset))
    end = result["samples"][-1]
    assert end["x"] == pytest.approx(0.0, abs=1e-6)
    assert end["y"] == pytest.approx(0.0, abs=1e-6)
    assert np.cos(end["heading"]) == pytest.approx(1.0, abs=1e-6)
    assert abs(end["v"]) < 1e-9


@pytest.mark.parametrize("speed,accel", [(1.0, 0.5), (2.0, 0.5), (3.0, 0.1)])
def test_fast_rovers_still_drive_the_planned_shapes(speed, accel):
    design = DESIGN.model_copy(update={"max_speed": speed, "max_accel": accel})
    result = rover.simulate(design, rover.preset_program(design, "square"))
    side = np.clip(6 * design.chassis_length, 0.6, 2.5)
    assert result["bounds"]["max_x"] == pytest.approx(side, abs=1e-6)
    assert result["bounds"]["max_y"] == pytest.approx(side, abs=1e-6)
    end = result["samples"][-1]
    assert (end["x"], end["y"]) == pytest.approx((0.0, 0.0), abs=1e-6)
    assert end["heading"] == pytest.approx(2 * np.pi, abs=1e-6)
    for step in rover.preset_program(design, "figure8"):
        assert step.duration >= max(abs(step.left), abs(step.right)) / accel - 1e-9


def test_square_has_expected_size_and_acceleration_limit():
    result = rover.simulate(DESIGN, rover.preset_program(DESIGN, "square"))
    side = np.clip(6 * DESIGN.chassis_length, 0.6, 2.5)
    assert result["bounds"]["max_x"] == pytest.approx(side, abs=1e-6)
    samples = result["samples"]
    for a, b in zip(samples, samples[1:], strict=False):
        dt = b["t"] - a["t"]
        if dt > 1e-6:
            assert abs(b["v"] - a["v"]) / dt <= DESIGN.max_accel * 1.01


def test_unknown_preset_rejected():
    with pytest.raises(ValueError):
        rover.preset_program(DESIGN, "moonwalk")
