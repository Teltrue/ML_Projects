import numpy as np
import pytest

from app.engines.mechanical.kinematics import (
    Body,
    DHLink,
    fk,
    forward_kinematics,
    gravity_torques,
    point_jacobian,
    rod_unit_inertia,
    unit_inertia_diagonal,
)

# A planar 2R arm lying in the x-y plane is the textbook check for DH code.
PLANAR = [DHLink(d=0.0, a=0.3, alpha=0.0), DHLink(d=0.0, a=0.2, alpha=0.0)]


def test_dh_forward_kinematics_matches_closed_form():
    rng = np.random.default_rng(0)
    for q in rng.uniform(-np.pi, np.pi, size=(20, 2)):
        ee = fk(PLANAR, q)[-1][:3, 3]
        expected = [0.3 * np.cos(q[0]) + 0.2 * np.cos(q[0] + q[1]),
                    0.3 * np.sin(q[0]) + 0.2 * np.sin(q[0] + q[1]), 0.0]
        assert ee == pytest.approx(expected, abs=1e-12)


def test_batched_and_single_pose_agree():
    q = np.array([[0.1, 0.2], [0.5, -1.0], [2.0, 0.3]])
    batch = forward_kinematics(PLANAR, q)
    for i in range(3):
        single = fk(PLANAR, q[i])
        for f_batch, f_single in zip(batch, single, strict=True):
            assert f_batch[i] == pytest.approx(f_single)


def test_point_jacobian_matches_finite_differences():
    links = [DHLink(0.1, 0.0, np.pi / 2), DHLink(0.0, 0.25, 0.0), DHLink(0.0, 0.2, 0.0)]
    q = np.array([0.3, 0.7, -1.1])
    frames = forward_kinematics(links, q[None])
    ee = frames[-1][:, :3, 3]
    jac = point_jacobian(frames, ee, 3)[0]
    eps = 1e-7
    for j in range(3):
        dq = q.copy()
        dq[j] += eps
        moved = fk(links, dq)[-1][:3, 3]
        assert (moved - ee[0]) / eps == pytest.approx(jac[:, j], abs=1e-5)


def test_gravity_torque_of_horizontal_planar_arm():
    # Rotate the planar arm into a vertical plane (joint axes horizontal) by tilting link 0.
    links = [DHLink(0.0, 0.0, np.pi / 2), DHLink(0.0, 0.3, 0.0), DHLink(0.0, 0.2, 0.0)]
    bodies = [Body("tip", 2.0, 3, np.zeros(3))]
    frames = forward_kinematics(links, np.array([[0.0, 0.0, 0.0]]))
    tau = gravity_torques(frames, bodies)[0]
    assert tau[1] == pytest.approx(2.0 * 9.81 * 0.5)
    assert tau[2] == pytest.approx(2.0 * 9.81 * 0.2)
    assert tau[0] == pytest.approx(0.0)


def test_rod_inertia_about_its_joint():
    # A rod of length L pivoting at one end has I = m L^2 / 3 about the pivot.
    links = [DHLink(0.0, 0.4, 0.0)]
    rod = Body("rod", 1.0, 1, np.array([-0.2, 0.0, 0.0]), rod_unit_inertia(0.4))
    frames = forward_kinematics(links, np.array([[0.3]]))
    assert unit_inertia_diagonal(frames, rod)[0, 0] == pytest.approx(0.4**2 / 3)
