"use client";

import { CircleCheck, Crosshair, Hand, TriangleAlert } from "lucide-react";
import { deg, kgcm } from "@/lib/format";
import { useStudio } from "@/lib/store";
import type { ArmDesign, Vec3 } from "@/lib/types";
import { Segmented, Toggle, UsageBar } from "../ui";
import { ParamGroup, ParamSlider } from "./ParamPanel";

const JOINT_LABELS = ["Base yaw", "Shoulder", "Elbow"];
const JOINT_ROLES = ["base", "shoulder", "elbow"];
const LIMITS: [number, number][] = [
  [-90, 90],
  [0, 180],
  [-180, 0],
];

export default function PosePanel() {
  const design = useStudio((s) => s.design) as ArmDesign;
  const mode = useStudio((s) => s.poseMode);
  const target = useStudio((s) => s.target);
  const joints = useStudio((s) => s.joints);
  const pose = useStudio((s) => s.pose);
  const gripperClosed = useStudio((s) => s.gripperClosed);
  const actuators = useStudio((s) => s.analysis?.electrical.actuators);
  const { setTarget, setJoints, setPoseMode, set } = useStudio.getState();

  const reach = design.upper_arm_length + design.forearm_length;
  const span = Math.ceil((reach + 0.02) * 100) * 10; // mm, rounded to the next cm

  const updateTarget = (i: number, v: number) => {
    const next = [...target] as Vec3;
    next[i] = v / 1000;
    setTarget(next);
  };
  const updateJoint = (i: number, v: number) => {
    const next = [...joints] as Vec3;
    next[i] = v;
    setJoints(next);
  };

  return (
    <ParamGroup title="Pose">
      <div className="mb-2 flex items-center justify-between">
        <Segmented
          size="sm"
          value={mode}
          onChange={setPoseMode}
          options={[
            {
              value: "ik",
              label: (
                <>
                  <Crosshair className="size-3" /> Target (IK)
                </>
              ),
            },
            {
              value: "fk",
              label: (
                <>
                  <Hand className="size-3" /> Joints (FK)
                </>
              ),
            },
          ]}
        />
      </div>
      {mode === "ik" ? (
        <>
          <p className="mb-1 text-[11px] text-ink-400">
            Drag the glowing target in the 3D view, or set it here.
          </p>
          {(["X", "Y", "Z"] as const).map((axis, i) => (
            <ParamSlider
              key={axis}
              label={`Target ${axis}`}
              unit="mm"
              value={Math.round(target[i] * 1000)}
              min={i === 2 ? 0 : -span}
              max={i === 2 ? Math.round((design.base_height + reach) * 1000) + 20 : span}
              step={1}
              onChange={(v) => updateTarget(i, v)}
            />
          ))}
        </>
      ) : (
        JOINT_LABELS.map((label, i) => (
          <ParamSlider
            key={label}
            label={label}
            unit="°"
            value={Math.round(joints[i])}
            min={LIMITS[i][0]}
            max={LIMITS[i][1]}
            step={1}
            onChange={(v) => updateJoint(i, v)}
          />
        ))
      )}
      <Toggle label="Gripper closed" checked={gripperClosed} onChange={(v) => set({ gripperClosed: v })} />
      {pose && (
        <div className="mt-2 space-y-2 rounded-lg border border-ink-800 bg-ink-950/60 p-2.5">
          <div className="flex items-start gap-1.5 text-[11px]">
            {pose.exact ? (
              <CircleCheck className="mt-px size-3.5 shrink-0 text-emerald-400" />
            ) : (
              <TriangleAlert className="mt-px size-3.5 shrink-0 text-amber-400" />
            )}
            <span className={pose.exact ? "text-ink-300" : "text-amber-200"}>{pose.message}</span>
          </div>
          {pose.warnings.map((w) => (
            <div key={w} className="flex items-start gap-1.5 text-[11px] text-amber-200">
              <TriangleAlert className="mt-px size-3.5 shrink-0 text-amber-400" />
              {w}
            </div>
          ))}
          <table className="w-full text-[11px] tabular-nums">
            <thead>
              <tr className="text-ink-400">
                <th className="text-left font-normal">Joint</th>
                <th className="text-right font-normal">Angle</th>
                <th className="text-right font-normal">Servo</th>
                <th className="w-24 pl-2 text-left font-normal">Holding torque</th>
              </tr>
            </thead>
            <tbody>
              {JOINT_LABELS.map((label, i) => {
                const act = actuators?.find((a) => a.role === JOINT_ROLES[i]);
                const need = pose.holding_torque_nm[i] / 0.0980665;
                return (
                  <tr key={label} className="text-ink-300">
                    <td className="py-0.5">{label}</td>
                    <td className="text-right">{deg(pose.q_deg[i], 0)}</td>
                    <td className="text-right text-ink-400">{deg(pose.servo_deg[i], 0)}</td>
                    <td className="pl-2" title={`${kgcm(need)} of ${act ? kgcm(act.available_kgcm) : "?"}`}>
                      <UsageBar value={need} max={act?.available_kgcm ?? need} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="text-[11px] text-ink-400">
            Gripper tip at ({pose.ee.map((v) => Math.round(v * 1000)).join(", ")}) mm
          </div>
        </div>
      )}
    </ParamGroup>
  );
}
