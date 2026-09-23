import type { ArmTrajectory, RoverSample, RoverSim, Vec3 } from "./types";

/**
 * The simulation clock. The render loop advances it every frame and the 3D models read it
 * directly, so playback doesn't push 60 store updates a second through React.
 */
export const clock = { time: 0 };

/** Index of the last sample with t <= time (samples are sorted by t). */
function bracket<T extends { t: number }>(samples: T[], time: number): [T, T, number] {
  if (time <= samples[0].t) return [samples[0], samples[0], 0];
  const last = samples[samples.length - 1];
  if (time >= last.t) return [last, last, 0];
  let lo = 0;
  let hi = samples.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (samples[mid].t <= time) lo = mid;
    else hi = mid;
  }
  const a = samples[lo];
  const b = samples[hi];
  const f = b.t > a.t ? (time - a.t) / (b.t - a.t) : 0;
  return [a, b, f];
}

const lerp = (a: number, b: number, f: number) => a + (b - a) * f;

export function armFrame(traj: ArmTrajectory, time: number) {
  const [a, b, f] = bracket(traj.samples, time);
  return {
    q: a.q.map((v, i) => lerp(v, b.q[i], f)) as Vec3,
    gripper: lerp(a.gripper, b.gripper, f),
    ee: a.ee.map((v, i) => lerp(v, b.ee[i], f)) as Vec3,
  };
}

export function roverFrame(sim: RoverSim, time: number): RoverSample {
  const [a, b, f] = bracket(sim.samples, time);
  return {
    t: time,
    x: lerp(a.x, b.x, f),
    y: lerp(a.y, b.y, f),
    heading: lerp(a.heading, b.heading, f),
    wheel_left: lerp(a.wheel_left, b.wheel_left, f),
    wheel_right: lerp(a.wheel_right, b.wheel_right, f),
    v: lerp(a.v, b.v, f),
    omega: lerp(a.omega, b.omega, f),
  };
}

export const DEG = Math.PI / 180;

/** Same closed form as the backend: gripper tip position for joint angles in degrees. */
export function armForward(
  d: { base_height: number; upper_arm_length: number; forearm_length: number },
  q: Vec3,
): Vec3 {
  const [t1, t2, t3] = q.map((v) => v * DEG);
  const r = d.upper_arm_length * Math.cos(t2) + d.forearm_length * Math.cos(t2 + t3);
  return [
    r * Math.cos(t1),
    r * Math.sin(t1),
    d.base_height + d.upper_arm_length * Math.sin(t2) + d.forearm_length * Math.sin(t2 + t3),
  ];
}
