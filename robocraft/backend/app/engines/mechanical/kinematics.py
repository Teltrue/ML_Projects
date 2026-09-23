"""Generic serial-chain kinematics and statics using standard Denavit-Hartenberg parameters.

Conventions
-----------
* Standard (distal) DH: frame ``i`` sits at the far end of link ``i`` and joint ``i + 1``
  rotates about the z-axis of frame ``i``.
* ``frames[0]`` is the fixed base frame, ``frames[i]`` is the pose of frame ``i``.
* All joints are revolute (enough for the MVP templates).
* World z points up; gravity acts along ``-z``.

Every function is batched over poses: joint arrays have shape ``(P, n)`` and each frame
has shape ``(P, 4, 4)``. That lets the arm template sweep hundreds of poses for worst-case
torque sizing in a few milliseconds. :func:`fk` is the single-pose convenience wrapper.
"""

from dataclasses import dataclass, field

import numpy as np

GRAVITY = 9.81  # m/s^2
UP = np.array([0.0, 0.0, GRAVITY])


@dataclass(frozen=True)
class DHLink:
    d: float
    a: float
    alpha: float
    theta_offset: float = 0.0


@dataclass(frozen=True)
class Body:
    """A rigid mass attached to link ``link`` (1-based; 0 means the fixed base).

    ``local_com`` is the centre of mass in that link's DH frame and ``unit_inertia`` is the
    inertia tensor about the COM *per kilogram*, so scaling the mass scales both terms.
    """

    name: str
    mass: float
    link: int
    local_com: np.ndarray
    unit_inertia: np.ndarray = field(default_factory=lambda: np.zeros((3, 3)))


def rod_unit_inertia(length: float) -> np.ndarray:
    """Slender rod lying along the local x-axis, inertia per kg about its centre."""
    i = length**2 / 12.0
    return np.diag([0.0, i, i])


def dh_transform(theta: np.ndarray, d: float, a: float, alpha: float) -> np.ndarray:
    theta = np.atleast_1d(theta)
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(alpha), np.sin(alpha)
    t = np.zeros((theta.shape[0], 4, 4))
    t[:, 0, 0], t[:, 0, 1], t[:, 0, 2], t[:, 0, 3] = ct, -st * ca, st * sa, a * ct
    t[:, 1, 0], t[:, 1, 1], t[:, 1, 2], t[:, 1, 3] = st, ct * ca, -ct * sa, a * st
    t[:, 2, 1], t[:, 2, 2], t[:, 2, 3] = sa, ca, d
    t[:, 3, 3] = 1.0
    return t


def forward_kinematics(links: list[DHLink], q: np.ndarray) -> list[np.ndarray]:
    """Frames ``[T0, T1, ..., Tn]`` (each ``(P, 4, 4)``) for joint angles ``q`` of shape (P, n)."""
    q = np.atleast_2d(q)
    t = np.broadcast_to(np.eye(4), (q.shape[0], 4, 4)).copy()
    frames = [t]
    for i, link in enumerate(links):
        t = t @ dh_transform(q[:, i] + link.theta_offset, link.d, link.a, link.alpha)
        frames.append(t)
    return frames


def fk(links: list[DHLink], q: np.ndarray) -> list[np.ndarray]:
    """Single-pose forward kinematics: returns ``[T0, ..., Tn]`` as plain 4x4 matrices."""
    return [f[0] for f in forward_kinematics(links, np.asarray(q, dtype=float)[None, :])]


def body_position(frames: list[np.ndarray], body: Body) -> np.ndarray:
    t = frames[body.link]
    return t[:, :3, :3] @ body.local_com + t[:, :3, 3]


def point_jacobian(frames: list[np.ndarray], points: np.ndarray, link: int) -> np.ndarray:
    """Linear-velocity Jacobian ``(P, 3, n)`` of points rigidly attached to ``link``."""
    p_count, n = points.shape[0], len(frames) - 1
    jac = np.zeros((p_count, 3, n))
    for j in range(link):
        z = frames[j][:, :3, 2]
        o = frames[j][:, :3, 3]
        jac[:, :, j] = np.cross(z, points - o)
    return jac


def angular_jacobian(frames: list[np.ndarray], link: int) -> np.ndarray:
    p_count, n = frames[0].shape[0], len(frames) - 1
    jac = np.zeros((p_count, 3, n))
    for j in range(link):
        jac[:, :, j] = frames[j][:, :3, 2]
    return jac


def unit_gravity_torque(frames: list[np.ndarray], body: Body) -> np.ndarray:
    """Holding torque ``(P, n)`` produced by 1 kg placed at ``body``'s centre of mass."""
    jv = point_jacobian(frames, body_position(frames, body), body.link)
    return np.einsum("pij,i->pj", jv, UP)


def unit_inertia_diagonal(frames: list[np.ndarray], body: Body) -> np.ndarray:
    """Diagonal of the joint-space inertia matrix ``(P, n)`` contributed by 1 kg of ``body``."""
    jv = point_jacobian(frames, body_position(frames, body), body.link)
    diag = np.einsum("pij,pij->pj", jv, jv)
    if body.unit_inertia.any():
        r = frames[body.link][:, :3, :3]
        world_inertia = r @ body.unit_inertia @ np.transpose(r, (0, 2, 1))
        jw = angular_jacobian(frames, body.link)
        diag = diag + np.einsum("pij,pik,pkj->pj", jw, world_inertia, jw)
    return diag


def gravity_torques(frames: list[np.ndarray], bodies: list[Body]) -> np.ndarray:
    """Joint torques ``(P, n)`` in N·m the actuators must supply to hold each pose."""
    p_count, n = frames[0].shape[0], len(frames) - 1
    tau = np.zeros((p_count, n))
    for body in bodies:
        if body.link > 0 and body.mass > 0:
            tau += body.mass * unit_gravity_torque(frames, body)
    return tau


def center_of_mass(frames: list[np.ndarray], bodies: list[Body]) -> tuple[np.ndarray, float]:
    """Combined centre of mass ``(P, 3)`` and total mass of ``bodies``."""
    total = float(sum(b.mass for b in bodies))
    weighted = np.zeros((frames[0].shape[0], 3))
    for body in bodies:
        weighted += body.mass * body_position(frames, body)
    return (weighted / total if total > 0 else weighted), total
