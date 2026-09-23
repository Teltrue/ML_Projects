"use client";

import { Html, Line, TransformControls } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { pct } from "@/lib/format";
import { armFrame, DEG } from "@/lib/playback";
import { useStudio } from "@/lib/store";
import type { Actuator, ArmDesign, Vec3 } from "@/lib/types";

const HOME: Vec3 = [0, 90, -90];
const STATUS_COLOR = { ok: "#34d399", marginal: "#fbbf24", insufficient: "#f87171" } as const;
const LINK = "#d7dee8";
const METAL = "#8b97a8";
const DARK = "#1c2533";
const PAYLOAD = 0.024;
const GRIP_OPEN = 0.05;
const GRIP_CLOSED = 0.03;

/** Servo body [along link, along joint axis, thickness] from its mass class. */
function housing(massKg?: number): Vec3 {
  if (!massKg || massKg < 0.02) return [0.024, 0.02, 0.013];
  if (massKg < 0.1) return [0.041, 0.034, 0.021];
  return [0.066, 0.05, 0.03];
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <div className="pointer-events-none rounded-md border border-ink-700 bg-ink-900/90 px-1.5 py-0.5 text-[10px] whitespace-nowrap text-ink-100 shadow">
      {children}
    </div>
  );
}

function ServoHousing({
  actuator,
  size,
  position,
  rotation,
  axis = "y",
}: {
  actuator?: Actuator;
  size: Vec3;
  position?: Vec3;
  rotation?: Vec3;
  axis?: "y" | "z";
}) {
  const [hover, setHover] = useState(false);
  const focus = useStudio((s) => s.focusActuator);
  const color = actuator ? STATUS_COLOR[actuator.status] : "#64748b";
  const onOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    setHover(true);
    document.body.style.cursor = "pointer";
  };
  const onOut = () => {
    setHover(false);
    document.body.style.cursor = "";
  };
  const hornPos: Vec3 = axis === "y" ? [0, size[1] / 2 + 0.002, 0] : [0, 0, size[2] / 2 + 0.002];
  return (
    <group position={position} rotation={rotation}>
      <mesh
        castShadow
        onPointerOver={onOver}
        onPointerOut={onOut}
        onClick={(e) => {
          e.stopPropagation();
          if (actuator) focus(actuator.role);
        }}
      >
        <boxGeometry args={size} />
        <meshStandardMaterial
          color={DARK}
          emissive={color}
          emissiveIntensity={hover ? 0.55 : 0.22}
          roughness={0.5}
        />
      </mesh>
      <mesh position={hornPos} rotation={axis === "y" ? [0, 0, 0] : [Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[size[0] * 0.28, size[0] * 0.28, 0.004, 24]} />
        <meshStandardMaterial color={color} roughness={0.4} />
      </mesh>
      {hover && actuator && (
        <Html position={[0, 0, size[2] + 0.02]} center zIndexRange={[20, 10]}>
          <Tag>
            <b>{actuator.label}</b> · {actuator.name}
            <br />
            {actuator.required_kgcm.toFixed(2)} / {actuator.available_kgcm.toFixed(1)} kg·cm (
            {pct(actuator.utilization)}) - click for details
          </Tag>
        </Html>
      )}
    </group>
  );
}

function Link({ length, width, height }: { length: number; width: number; height: number }) {
  return (
    <mesh position={[length / 2, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={[length, width, height]} />
      <meshStandardMaterial color={LINK} metalness={0.35} roughness={0.35} />
    </mesh>
  );
}

function arc(radius: number, from: number, to: number, plane: "xz" | "xy", offset: Vec3 = [0, 0, 0]) {
  const pts: Vec3[] = [];
  const n = 64;
  for (let i = 0; i <= n; i++) {
    const a = from + ((to - from) * i) / n;
    const u = radius * Math.cos(a);
    const v = radius * Math.sin(a);
    pts.push(
      plane === "xz" ? [offset[0] + u, offset[1], offset[2] + v] : [offset[0] + u, offset[1] + v, offset[2]],
    );
  }
  return pts;
}

/** Faint reach hemisphere plus the arc where the gripper can touch the table. */
function ReachShell({ design }: { design: ArmDesign }) {
  const max = design.upper_arm_length + design.forearm_length;
  const table = max > design.base_height ? Math.sqrt(max ** 2 - design.base_height ** 2) : 0;
  return (
    <>
      <group position={[0, 0, design.base_height]} rotation={[Math.PI / 2, 0, 0]}>
        {/* phi in [pi/2, 3pi/2] is the half-space in front of the robot (base yaw limits). */}
        <mesh>
          <sphereGeometry args={[max, 48, 24, Math.PI / 2, Math.PI]} />
          <meshBasicMaterial
            color="#3dd6ec"
            transparent
            opacity={0.03}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      </group>
      {table > 0.01 && (
        <Line
          points={arc(table, -Math.PI / 2, Math.PI / 2, "xy", [0, 0, 0.002])}
          color="#3dd6ec"
          dashed
          dashSize={0.012}
          gapSize={0.008}
          transparent
          opacity={0.55}
        />
      )}
    </>
  );
}

/** The reachable band in the arm's current vertical plane; rotates with the base. */
function ReachSlice({ design }: { design: ArmDesign }) {
  const max = design.upper_arm_length + design.forearm_length;
  const min = Math.abs(design.upper_arm_length - design.forearm_length);
  const lower = -Math.min(Math.PI / 2, Math.asin(Math.min(design.base_height / max, 1)));
  return (
    <group position={[0, 0, design.base_height]}>
      <Line points={arc(max, lower, Math.PI / 2, "xz")} color="#3dd6ec" transparent opacity={0.5} />
      {min > 0.01 && (
        <Line points={arc(min, -Math.PI / 2, Math.PI / 2, "xz")} color="#f87171" transparent opacity={0.5} />
      )}
    </group>
  );
}

/** Robot frame (z up) <-> three.js world (y up). */
const toWorld = ([x, y, z]: Vec3): Vec3 => [x, z, -y];
const toRobot = ([x, y, z]: Vec3): Vec3 => [x, -z, y];

/** Draggable IK target. Lives in world space: the gizmo misbehaves under a rotated parent. */
function IkTarget() {
  const target = useStudio((s) => s.target);
  const exact = useStudio((s) => s.pose?.exact ?? true);
  const ee = useStudio((s) => s.pose?.ee);
  const setTarget = useStudio((s) => s.setTarget);
  const ref = useRef<THREE.Mesh>(null!);
  const color = exact ? "#3dd6ec" : "#fbbf24";
  return (
    <>
      <mesh ref={ref} position={toWorld(target)}>
        <sphereGeometry args={[0.009, 24, 16]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.2} />
      </mesh>
      <TransformControls
        object={ref}
        mode="translate"
        size={0.55}
        onMouseDown={() => useStudio.setState({ dragging: true })}
        onMouseUp={() => useStudio.setState({ dragging: false })}
        onObjectChange={() => {
          const p = ref.current.position;
          const [x, y, z] = toRobot([p.x, p.y, p.z]);
          setTarget([x, y, Math.max(z, 0)]);
        }}
      />
      {ee && !exact && (
        <Line
          points={[toWorld(ee), toWorld(target)]}
          color="#fbbf24"
          dashed
          dashSize={0.01}
          gapSize={0.006}
        />
      )}
    </>
  );
}

function CenterOfMass() {
  const com = useStudio((s) => s.pose?.com);
  const stable = useStudio((s) => s.pose?.stable ?? true);
  if (!com) return null;
  return (
    <group>
      <mesh position={com}>
        <sphereGeometry args={[0.006, 16, 12]} />
        <meshBasicMaterial color={stable ? "#e879f9" : "#f87171"} />
      </mesh>
      <Line
        points={[com, [com[0], com[1], 0.001]]}
        color={stable ? "#e879f9" : "#f87171"}
        dashed
        dashSize={0.008}
        gapSize={0.005}
        transparent
        opacity={0.7}
      />
    </group>
  );
}

export default function ArmModel() {
  const design = useStudio((s) => s.design) as ArmDesign;
  const actuators = useStudio((s) => s.analysis?.electrical.actuators);
  const showDims = useStudio((s) => s.showDimensions);
  const showReach = useStudio((s) => s.showReach);
  const poseMode = useStudio((s) => s.poseMode);
  const sim = useStudio((s) => (s.sim?.kind === "arm" ? s.sim.data : null));
  const stable = useStudio((s) => s.pose?.stable ?? true);

  const yaw = useRef<THREE.Group>(null!);
  const shoulder = useRef<THREE.Group>(null!);
  const elbow = useRef<THREE.Group>(null!);
  const fingerL = useRef<THREE.Mesh>(null!);
  const fingerR = useRef<THREE.Mesh>(null!);
  const payload = useRef<THREE.Group>(null!);

  const byRole = useMemo(() => Object.fromEntries((actuators ?? []).map((a) => [a.role, a])), [actuators]);
  const d1 = design.base_height;
  const l1 = design.upper_arm_length;
  const l2 = design.forearm_length;
  const linkW = Math.min(Math.max(0.1 * (l1 + l2), 0.016), 0.032);
  const baseH = housing(byRole.base?.mass_kg);
  const shoulderH = housing(byRole.shoulder?.mass_kg);
  const elbowH = housing(byRole.elbow?.mass_kg);
  const gripH = housing(byRole.gripper?.mass_kg);
  const plateTop = 0.012;
  const turntableZ = plateTop + baseH[1];
  const columnH = Math.max(d1 - turntableZ - 0.006, 0.002);

  const events = useMemo(() => {
    if (!sim) return null;
    const at = (label: string) => sim.waypoints.find((w) => w.label === label);
    const pick = at("pick");
    const place = at("place");
    if (!pick || !place) return null;
    return { pickT: pick.t, placeT: place.t, pick: pick.position, place: place.position };
  }, [sim]);

  useFrame(() => {
    const st = useStudio.getState();
    let q = st.pose?.q_deg ?? HOME;
    let g = st.gripperClosed ? 1 : 0;
    let carry: Vec3 | null = null;
    let carried = false;
    if (st.sim?.kind === "arm") {
      const f = armFrame(st.sim.data, st.simTime);
      q = f.q;
      g = f.gripper;
      if (events) {
        if (st.simTime <= events.pickT || (g <= 0.5 && st.simTime < events.placeT)) {
          carry = events.pick;
        } else if (g > 0.5) {
          carry = f.ee;
          carried = true;
        } else {
          carry = events.place;
        }
      }
    } else if (st.gripperClosed && st.design?.template === "arm" && st.design.payload_mass > 0) {
      carry = st.pose?.ee ?? null;
      carried = true;
    }
    yaw.current.rotation.z = q[0] * DEG;
    shoulder.current.rotation.y = -q[1] * DEG;
    elbow.current.rotation.y = -q[2] * DEG;
    const gap = GRIP_OPEN + (GRIP_CLOSED - GRIP_OPEN) * g;
    fingerL.current.position.y = gap / 2;
    fingerR.current.position.y = -gap / 2;
    payload.current.visible = carry !== null;
    if (carry) {
      payload.current.position.set(carry[0], carry[1], carry[2]);
      payload.current.rotation.z = carried ? q[0] * DEG : 0;
    }
  });

  const trail = useMemo(() => sim?.samples.map((s) => s.ee) ?? null, [sim]);

  return (
    <>
      <group rotation={[-Math.PI / 2, 0, 0]}>
        {/* Base plate and footprint ring used by the tip-over check */}
        <mesh position={[0, 0, plateTop / 2]} rotation={[Math.PI / 2, 0, 0]} receiveShadow castShadow>
          <cylinderGeometry args={[design.base_radius, design.base_radius * 1.04, plateTop, 48]} />
          <meshStandardMaterial color="#263245" roughness={0.7} />
        </mesh>
        <mesh position={[0, 0, 0.0015]}>
          <ringGeometry args={[design.base_radius * 1.05, design.base_radius * 1.1, 64]} />
          <meshBasicMaterial color={stable ? "#34d399" : "#f87171"} transparent opacity={0.6} />
        </mesh>
        <ServoHousing
          actuator={byRole.base}
          size={[baseH[0], baseH[2], baseH[1]]}
          position={[0, 0, plateTop + baseH[1] / 2]}
          axis="z"
        />

        <group ref={yaw}>
          <mesh position={[0, 0, turntableZ + 0.003]} rotation={[Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry
              args={[
                Math.min(design.base_radius * 0.75, 0.05),
                Math.min(design.base_radius * 0.75, 0.05),
                0.006,
                40,
              ]}
            />
            <meshStandardMaterial color={METAL} metalness={0.6} roughness={0.3} />
          </mesh>
          <mesh position={[0, 0, turntableZ + 0.006 + columnH / 2]} castShadow>
            <boxGeometry args={[linkW * 1.3, shoulderH[1] + 0.012, columnH]} />
            <meshStandardMaterial color={LINK} metalness={0.35} roughness={0.35} />
          </mesh>

          {showReach && <ReachSlice design={design} />}
          <group position={[0, 0, d1]}>
            <group ref={shoulder}>
              <ServoHousing actuator={byRole.shoulder} size={[shoulderH[0], shoulderH[1], shoulderH[2]]} />
              <Link length={l1} width={linkW} height={linkW * 0.45} />
              {showDims && (
                <Html position={[l1 / 2, 0, linkW]} center zIndexRange={[20, 10]}>
                  <Tag>upper arm {Math.round(l1 * 1000)} mm</Tag>
                </Html>
              )}
              <group position={[l1, 0, 0]}>
                <group ref={elbow}>
                  <ServoHousing actuator={byRole.elbow} size={[elbowH[0], elbowH[1], elbowH[2]]} />
                  <Link length={l2 - 0.02} width={linkW * 0.85} height={linkW * 0.4} />
                  {showDims && (
                    <Html position={[l2 / 2, 0, linkW]} center zIndexRange={[20, 10]}>
                      <Tag>forearm {Math.round(l2 * 1000)} mm</Tag>
                    </Html>
                  )}
                  {/* Gripper: palm, micro servo and two fingers around the gripping point */}
                  <group position={[l2, 0, 0]}>
                    <mesh position={[-0.03, 0, 0]} castShadow>
                      <boxGeometry args={[0.012, GRIP_OPEN + 0.012, 0.014]} />
                      <meshStandardMaterial color={METAL} metalness={0.5} roughness={0.35} />
                    </mesh>
                    <ServoHousing
                      actuator={byRole.gripper}
                      size={[gripH[0] * 0.8, gripH[1] * 0.8, gripH[2] * 0.8]}
                      position={[-0.03, 0, 0.016]}
                      axis="z"
                    />
                    <mesh ref={fingerL} position={[-0.012, GRIP_OPEN / 2, 0]} castShadow>
                      <boxGeometry args={[0.036, 0.005, 0.012]} />
                      <meshStandardMaterial color={LINK} metalness={0.3} roughness={0.4} />
                    </mesh>
                    <mesh ref={fingerR} position={[-0.012, -GRIP_OPEN / 2, 0]} castShadow>
                      <boxGeometry args={[0.036, 0.005, 0.012]} />
                      <meshStandardMaterial color={LINK} metalness={0.3} roughness={0.4} />
                    </mesh>
                  </group>
                </group>
              </group>
            </group>
          </group>
          {showDims && (
            <Html position={[0, -(shoulderH[1] / 2 + 0.03), d1 / 2]} center zIndexRange={[20, 10]}>
              <Tag>shoulder {Math.round(d1 * 1000)} mm</Tag>
            </Html>
          )}
        </group>

        <group ref={payload} visible={false}>
          <mesh castShadow>
            <boxGeometry args={[PAYLOAD, PAYLOAD, PAYLOAD]} />
            <meshStandardMaterial color="#f59e0b" roughness={0.55} />
          </mesh>
        </group>
        {events && events.pick[2] > PAYLOAD && (
          <>
            <Pedestal at={events.pick} />
            <Pedestal at={events.place} />
          </>
        )}

        {showReach && <ReachShell design={design} />}
        {trail && <Line points={trail} color="#3dd6ec" transparent opacity={0.45} lineWidth={1.5} />}
        {!sim && <CenterOfMass />}
      </group>
      {!sim && poseMode === "ik" && <IkTarget />}
    </>
  );
}

function Pedestal({ at }: { at: Vec3 }) {
  const h = at[2] - PAYLOAD / 2;
  return (
    <mesh position={[at[0], at[1], h / 2]} rotation={[Math.PI / 2, 0, 0]} receiveShadow castShadow>
      <cylinderGeometry args={[0.02, 0.024, h, 24]} />
      <meshStandardMaterial color="#334155" roughness={0.8} />
    </mesh>
  );
}
