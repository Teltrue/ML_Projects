"use client";

import { kgcm, mass, mm } from "@/lib/format";
import { useStudio } from "@/lib/store";
import type { Actuator, ArmDesign, ArmMechanical, RoverDesign, RoverMechanical } from "@/lib/types";
import { Card, SectionTitle, Stat, UsageBar } from "../ui";

function Note({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-[11px] leading-relaxed text-ink-400">{children}</p>;
}

function ArmMechanics({
  mech,
  design,
  actuators,
}: {
  mech: ArmMechanical;
  design: ArmDesign;
  actuators: Actuator[];
}) {
  const byRole = Object.fromEntries(actuators.map((a) => [a.role, a]));
  const ext = mech.stability.extended;
  return (
    <div className="space-y-5">
      <section>
        <SectionTitle>Denavit-Hartenberg model</SectionTitle>
        <div className="overflow-x-auto rounded-lg border border-ink-800">
          <table className="w-full text-xs tabular-nums">
            <thead className="bg-ink-850 text-[11px] text-ink-400">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium">Joint</th>
                <th className="px-2 py-1.5 text-right font-medium">θ</th>
                <th className="px-2 py-1.5 text-right font-medium">d</th>
                <th className="px-2 py-1.5 text-right font-medium">a</th>
                <th className="px-2 py-1.5 text-right font-medium">α</th>
                <th className="px-2 py-1.5 text-right font-medium">Range</th>
              </tr>
            </thead>
            <tbody>
              {mech.dh_table.map((row) => (
                <tr key={row.joint} className="border-t border-ink-800 text-ink-300">
                  <td className="px-2 py-1.5 text-ink-100">{row.name}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{row.theta}</td>
                  <td className="px-2 py-1.5 text-right">{mm(row.d)}</td>
                  <td className="px-2 py-1.5 text-right">{mm(row.a)}</td>
                  <td className="px-2 py-1.5 text-right">{row.alpha_deg}°</td>
                  <td className="px-2 py-1.5 text-right text-ink-400">
                    {row.limits_deg[0]}…{row.limits_deg[1]}°
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Note>
          Standard DH convention: each row is Rot<sub>z</sub>(θ)·Trans<sub>z</sub>(d)·Trans<sub>x</sub>(a)·Rot
          <sub>x</sub>(α). Forward kinematics chains these transforms; inverse kinematics is solved in closed
          form (elbow-up preferred).
        </Note>
      </section>

      <section>
        <SectionTitle>Joint torque budget</SectionTitle>
        <div className="space-y-2">
          {mech.joints.map((j) => {
            const act = byRole[j.name];
            return (
              <Card key={j.name} className="p-2.5">
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="font-medium text-ink-100">{j.label}</span>
                  <span className="text-ink-300 tabular-nums">
                    needs <b className="text-ink-100">{kgcm(j.required_kgcm)}</b>
                    {act && <> of {kgcm(act.available_kgcm)}</>}
                  </span>
                </div>
                {act && (
                  <div className="mt-1.5">
                    <UsageBar
                      value={j.required_kgcm}
                      max={act.available_kgcm}
                      label={`${Math.round(act.utilization * 100)}%`}
                    />
                  </div>
                )}
                <div className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] text-ink-400 tabular-nums">
                  {j.name === "gripper" ? (
                    <span>squeeze force to hold the payload by friction</span>
                  ) : (
                    <>
                      <span>gravity {(j.gravity_nm * 1000).toFixed(0)} mN·m</span>
                      <span>inertia {(j.inertial_nm * 1000).toFixed(0)} mN·m</span>
                      <span>worst pose ({j.worst_pose_deg.map((v) => `${Math.round(v)}°`).join(", ")})</span>
                    </>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
        <Note>
          Worst case over a 5° sweep of the shoulder/elbow range: gravity via the Jacobian transpose (τ = Σ
          Jᵀ·m·g) plus inertia from the mass matrix (M(q)·α at your max acceleration), times the{" "}
          {design.safety_factor}× safety factor. Servo masses are fed back until the selection is stable.
        </Note>
      </section>

      <section>
        <SectionTitle>Workspace &amp; payload</SectionTitle>
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Max reach" value={mm(mech.reach.max)} />
          <Stat label="Min reach" value={mm(mech.reach.min)} />
          <Stat label="Moving mass" value={mass(mech.moving_mass_kg)} />
        </div>
        <Card className="mt-2 p-2.5">
          <div className="mb-1.5 flex justify-between text-xs">
            <span className="text-ink-300">Payload vs. what the servos can hold</span>
            <span className="text-ink-100 tabular-nums">
              {mass(design.payload_mass)} / {mass(mech.max_payload_kg)}
            </span>
          </div>
          <UsageBar value={design.payload_mass} max={mech.max_payload_kg} />
        </Card>
      </section>

      <section>
        <SectionTitle>Tip-over stability (fully extended)</SectionTitle>
        <Card className="p-2.5">
          <div className="mb-1.5 flex justify-between text-xs">
            <span className="text-ink-300">Centre of mass offset vs. base radius</span>
            <span className="text-ink-100 tabular-nums">
              {mm(ext.horizontal_offset_m)} / {mm(ext.base_radius_m)}
            </span>
          </div>
          <UsageBar value={ext.horizontal_offset_m} max={ext.base_radius_m} />
          <p className="mt-1.5 text-[11px] text-ink-400">
            {ext.stable
              ? "The combined centre of mass stays over the base even with the payload at full reach."
              : `Add ≈${Math.ceil(ext.ballast_kg * 1000)} g of ballast at the base, widen it, or clamp it down.`}
          </p>
        </Card>
      </section>
    </div>
  );
}

function RoverMechanics({ mech, design }: { mech: RoverMechanical; design: RoverDesign }) {
  const massColors: Record<string, string> = {
    chassis: "#64748b",
    payload: "#f59e0b",
    motors: "#34d399",
    battery: "#3b82f6",
    driver: "#ef4444",
    electronics: "#a78bfa",
  };
  const forces = [
    { label: "Rolling resistance", value: mech.forces_n.rolling },
    { label: `Climbing ${design.max_incline}°`, value: mech.forces_n.grade },
    { label: `Accelerating ${design.max_accel} m/s²`, value: mech.forces_n.acceleration },
  ];
  const k = mech.kinematics;
  return (
    <div className="space-y-5">
      <section>
        <SectionTitle>Mass budget · {mass(mech.total_mass_kg)}</SectionTitle>
        <div className="flex h-3 overflow-hidden rounded-full">
          {Object.entries(mech.mass_breakdown_kg).map(([key, v]) => (
            <div
              key={key}
              title={`${key}: ${mass(v)}`}
              style={{ width: `${(v / mech.total_mass_kg) * 100}%`, background: massColors[key] }}
            />
          ))}
        </div>
        <div className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1 text-[11px] text-ink-300">
          {Object.entries(mech.mass_breakdown_kg).map(([key, v]) => (
            <span key={key} className="flex items-center gap-1.5 capitalize">
              <span className="size-2 rounded-full" style={{ background: massColors[key] }} />
              {key} <span className="ml-auto text-ink-400 tabular-nums">{mass(v)}</span>
            </span>
          ))}
        </div>
        <Note>Motors, battery and driver masses come from the parts the Electrical Engine picked.</Note>
      </section>

      <section>
        <SectionTitle>Drive force budget · {mech.forces_n.total.toFixed(2)} N</SectionTitle>
        <div className="space-y-2">
          {forces.map((f) => (
            <div key={f.label}>
              <div className="mb-1 flex justify-between text-xs text-ink-300">
                <span>{f.label}</span>
                <span className="tabular-nums">{f.value.toFixed(2)} N</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-ink-800">
                <div
                  className="h-full rounded-full bg-brand-400"
                  style={{ width: `${(f.value / mech.forces_n.total) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <Note>
          F = m·g·(C<sub>rr</sub>·cos θ + sin θ) + m·a, shared between {design.drive_motors} motors, times the{" "}
          {design.safety_factor}× safety factor.
        </Note>
      </section>

      <section>
        <SectionTitle>Each motor must deliver</SectionTitle>
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Wheel speed" value={`${Math.round(mech.wheel_rpm)} RPM`} />
          <Stat label="Torque" value={kgcm(mech.torque_per_motor_kgcm)} />
          <Stat label="Power" value={`${mech.power_per_motor_w.toFixed(1)} W`} />
        </div>
      </section>

      <section>
        <SectionTitle>Traction</SectionTitle>
        <Card className="p-2.5">
          <div className="mb-1.5 flex justify-between text-xs">
            <span className="text-ink-300">Grip needed vs. available</span>
            <span className="text-ink-100 tabular-nums">
              {mech.traction.required_n.toFixed(1)} / {mech.traction.available_n.toFixed(1)} N
            </span>
          </div>
          <UsageBar value={mech.traction.required_n} max={mech.traction.available_n} />
        </Card>
      </section>

      <section>
        <SectionTitle>Differential-drive kinematics</SectionTitle>
        <Card className="space-y-1 p-2.5 font-mono text-[11px] text-ink-300">
          <div>
            v = (v<sub>R</sub> + v<sub>L</sub>) / 2
          </div>
          <div>
            ω = (v<sub>R</sub> − v<sub>L</sub>) / W, W = {mm(design.track_width)}
          </div>
        </Card>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <Stat label="Max turn rate" value={`${Math.round(k.max_yaw_rate_dps)}°/s`} />
          <Stat label="Full spin" value={`${k.spin_360_s.toFixed(2)} s`} />
          <Stat label="Braking distance" value={`${(k.stopping_distance_m * 100).toFixed(0)} cm`} />
          <Stat
            label="Obstacle stop at"
            value={mech.obstacle_stop_m ? `${Math.round(mech.obstacle_stop_m * 100)} cm` : "no sensor"}
          />
        </div>
      </section>
    </div>
  );
}

export default function MechanicsTab() {
  const analysis = useStudio((s) => s.analysis);
  const design = useStudio((s) => s.design);
  if (!analysis || !design) return null;
  return analysis.mechanical.template === "arm" ? (
    <ArmMechanics
      mech={analysis.mechanical}
      design={design as ArmDesign}
      actuators={analysis.electrical.actuators}
    />
  ) : (
    <RoverMechanics mech={analysis.mechanical} design={design as RoverDesign} />
  );
}
