"use client";

import { Html, Line, RoundedBox } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { pct } from "@/lib/format";
import { roverFrame } from "@/lib/playback";
import { useStudio } from "@/lib/store";
import type { Actuator, RoverDesign } from "@/lib/types";

const STATUS_COLOR = { ok: "#34d399", marginal: "#fbbf24", insufficient: "#f87171" } as const;

function motorRadius(massKg?: number) {
  if (!massKg || massKg < 0.02) return 0.0065; // N20
  if (massKg < 0.05) return 0.011; // TT
  if (massKg < 0.12) return 0.0125; // 25 mm
  return 0.0185; // 37 mm
}

function Wheel({ radius, width, side }: { radius: number; width: number; side: 1 | -1 }) {
  // Tagged so the animation loop can spin it without holding refs.
  return (
    <group userData={{ wheel: side === 1 ? "left" : "right" }}>
      <mesh castShadow>
        <cylinderGeometry args={[radius, radius, width, 40]} />
        <meshStandardMaterial color="#141a22" roughness={0.9} />
      </mesh>
      <mesh position={[0, (side * width) / 2 + side * 0.0005, 0]}>
        <cylinderGeometry args={[radius * 0.62, radius * 0.62, 0.002, 32]} />
        <meshStandardMaterial color="#aab4c3" metalness={0.5} roughness={0.35} />
      </mesh>
      {[0, 1, 2].map((k) => (
        <mesh
          key={k}
          position={[0, (side * width) / 2 + side * 0.0016, 0]}
          rotation={[0, (k * Math.PI) / 3, 0]}
        >
          <boxGeometry args={[radius * 1.15, 0.0015, radius * 0.14]} />
          <meshStandardMaterial color="#3dd6ec" emissive="#3dd6ec" emissiveIntensity={0.25} />
        </mesh>
      ))}
    </group>
  );
}

function Motor({
  actuator,
  position,
  length,
  radius,
}: {
  actuator?: Actuator;
  position: [number, number, number];
  length: number;
  radius: number;
}) {
  const [hover, setHover] = useState(false);
  const focus = useStudio((s) => s.focusActuator);
  const color = actuator ? STATUS_COLOR[actuator.status] : "#64748b";
  return (
    <group position={position}>
      <mesh
        castShadow
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          setHover(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHover(false);
          document.body.style.cursor = "";
        }}
        onClick={(e) => {
          e.stopPropagation();
          if (actuator) focus(actuator.role);
        }}
      >
        <cylinderGeometry args={[radius, radius, length, 24]} />
        <meshStandardMaterial
          color="#9aa6b6"
          metalness={0.6}
          roughness={0.35}
          emissive={color}
          emissiveIntensity={hover ? 0.6 : 0.25}
        />
      </mesh>
      {hover && actuator && (
        <Html position={[0, 0, radius + 0.03]} center zIndexRange={[20, 10]}>
          <div className="pointer-events-none rounded-md border border-ink-700 bg-ink-900/90 px-1.5 py-0.5 text-[10px] whitespace-nowrap text-ink-100 shadow">
            <b>{actuator.name}</b>
            <br />
            {actuator.required_kgcm.toFixed(2)} / {actuator.available_kgcm.toFixed(2)} kg·cm at{" "}
            {Math.round(Number(actuator.extra.wheel_rpm))} RPM ({pct(actuator.utilization)})
          </div>
        </Html>
      )}
    </group>
  );
}

export default function RoverModel() {
  const design = useStudio((s) => s.design) as RoverDesign;
  const actuator = useStudio((s) => s.analysis?.electrical.actuators[0]);
  const driverId = useStudio((s) => s.analysis?.electrical.driver_id);
  const stopM = useStudio((s) =>
    s.analysis?.mechanical.template === "rover" ? s.analysis.mechanical.obstacle_stop_m : null,
  );
  const showDims = useStudio((s) => s.showDimensions);
  const sim = useStudio((s) => (s.sim?.kind === "rover" ? s.sim.data : null));

  const body = useRef<THREE.Group>(null!);

  const r = design.wheel_diameter / 2;
  const L = design.chassis_length;
  const W = design.chassis_width;
  const T = design.track_width;
  const four = design.drive_motors === 4;
  const wheelW = Math.min(0.25 * design.wheel_diameter + 0.01, 0.06);
  // The simulated pose is the point midway between the drive wheels.
  const axles = four ? [Math.max(L / 2 - r * 0.9, r * 0.7), -Math.max(L / 2 - r * 0.9, r * 0.7)] : [0];
  const chassisX = four ? 0 : L / 2 - r - 0.01;
  const deckZ = Math.max(r * 0.95, 0.02);
  const deckH = 0.006;
  const top = deckZ + deckH / 2;
  const mRadius = motorRadius(actuator?.mass_kg);
  const mLength = Math.min(Math.max(T / 2 - wheelW / 2 - 0.004, 0.015), 0.07);
  const frontX = chassisX + L / 2;

  useFrame(() => {
    const st = useStudio.getState();
    const f = st.sim?.kind === "rover" ? roverFrame(st.sim.data, st.simTime) : null;
    body.current.position.set(f?.x ?? 0, f?.y ?? 0, 0);
    body.current.rotation.z = f?.heading ?? 0;
    body.current.traverse((o) => {
      if (o.userData.wheel === "left") o.rotation.y = f?.wheel_left ?? 0;
      else if (o.userData.wheel === "right") o.rotation.y = f?.wheel_right ?? 0;
    });
  });

  const path = useMemo(
    () => sim?.samples.map((s) => [s.x, s.y, 0.002] as [number, number, number]) ?? null,
    [sim],
  );

  return (
    <group rotation={[-Math.PI / 2, 0, 0]}>
      <group ref={body}>
        {/* Deck */}
        <RoundedBox
          args={[L, W, deckH]}
          radius={0.0025}
          position={[chassisX, 0, deckZ]}
          castShadow
          receiveShadow
        >
          <meshStandardMaterial color="#1f2a3a" roughness={0.6} />
        </RoundedBox>
        <mesh position={[chassisX, 0, top + 0.0005]}>
          <boxGeometry args={[L * 0.96, W * 0.9, 0.001]} />
          <meshStandardMaterial color="#16b8d2" transparent opacity={0.18} />
        </mesh>

        {/* Electronics on the deck */}
        <mesh position={[chassisX - L * 0.22, 0, top + 0.012]} castShadow>
          <boxGeometry args={[Math.min(L * 0.3, 0.1), Math.min(W * 0.5, 0.045), 0.024]} />
          <meshStandardMaterial color="#1e3a8a" roughness={0.5} />
        </mesh>
        <mesh position={[chassisX + L * 0.08, W * 0.18, top + 0.004]} castShadow>
          <boxGeometry args={[Math.min(L * 0.3, 0.068), Math.min(W * 0.35, 0.053), 0.008]} />
          <meshStandardMaterial color="#0f766e" roughness={0.6} />
        </mesh>
        <mesh position={[chassisX + L * 0.08, -W * 0.2, top + 0.01]} castShadow>
          <boxGeometry args={[0.043, 0.043, driverId === "l298n" ? 0.02 : 0.008]} />
          <meshStandardMaterial color={driverId === "l298n" ? "#b91c1c" : "#6d28d9"} roughness={0.5} />
        </mesh>

        {/* Wheels and motors */}
        {axles.map((ax, i) =>
          ([1, -1] as const).map((side) => (
            <group key={`${i}-${side}`}>
              <group position={[ax, (side * T) / 2, r]}>
                <Wheel radius={r} width={wheelW} side={side} />
              </group>
              <Motor
                actuator={actuator}
                position={[ax, side * (T / 2 - wheelW / 2 - mLength / 2 - 0.001), r]}
                length={mLength}
                radius={mRadius}
              />
            </group>
          )),
        )}
        {!four && (
          <group position={[chassisX + L / 2 - 0.025, 0, 0]}>
            <mesh position={[0, 0, Math.min(0.012, deckZ / 2)]} castShadow>
              <sphereGeometry args={[Math.min(0.012, deckZ / 2), 20, 16]} />
              <meshStandardMaterial color="#cbd5e1" metalness={0.8} roughness={0.2} />
            </mesh>
            <mesh position={[0, 0, (deckZ + Math.min(0.012, deckZ / 2)) / 2]}>
              <boxGeometry args={[0.012, 0.012, Math.max(deckZ - Math.min(0.012, deckZ / 2), 0.002)]} />
              <meshStandardMaterial color="#475569" />
            </mesh>
          </group>
        )}

        {/* Ultrasonic sensor and its stopping zone */}
        {design.obstacle_sensor && (
          <group position={[frontX - 0.004, 0, top + 0.012]}>
            <mesh castShadow>
              <boxGeometry args={[0.004, 0.045, 0.02]} />
              <meshStandardMaterial color="#1d4ed8" />
            </mesh>
            {[-1, 1].map((k) => (
              <mesh key={k} position={[0.006, k * 0.013, 0]} rotation={[0, 0, Math.PI / 2]}>
                <cylinderGeometry args={[0.008, 0.008, 0.012, 20]} />
                <meshStandardMaterial color="#cbd5e1" metalness={0.8} roughness={0.25} />
              </mesh>
            ))}
            {stopM && (
              <mesh position={[stopM / 2 + 0.01, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
                <coneGeometry args={[Math.tan((15 * Math.PI) / 180) * stopM, stopM, 32, 1, true]} />
                <meshBasicMaterial
                  color="#3dd6ec"
                  transparent
                  opacity={0.05}
                  side={THREE.DoubleSide}
                  depthWrite={false}
                />
              </mesh>
            )}
          </group>
        )}

        {showDims && (
          <>
            <Html position={[chassisX, -(T / 2 + wheelW), deckZ]} center zIndexRange={[20, 10]}>
              <div className="pointer-events-none rounded-md border border-ink-700 bg-ink-900/90 px-1.5 py-0.5 text-[10px] whitespace-nowrap text-ink-100">
                {Math.round(L * 1000)} × {Math.round(W * 1000)} mm · track {Math.round(T * 1000)} mm
              </div>
            </Html>
            <Html position={[axles[0], T / 2 + wheelW, r * 2 + 0.01]} center zIndexRange={[20, 10]}>
              <div className="pointer-events-none rounded-md border border-ink-700 bg-ink-900/90 px-1.5 py-0.5 text-[10px] whitespace-nowrap text-ink-100">
                ⌀ {Math.round(design.wheel_diameter * 1000)} mm
              </div>
            </Html>
          </>
        )}
      </group>

      {path && <Line points={path} color="#3dd6ec" transparent opacity={0.55} lineWidth={2} />}
    </group>
  );
}
