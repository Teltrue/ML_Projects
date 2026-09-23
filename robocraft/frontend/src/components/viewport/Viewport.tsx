"use client";

import { Grid, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { clock } from "@/lib/playback";
import { useStudio } from "@/lib/store";
import type { ArmDesign, RoverDesign, TemplateId } from "@/lib/types";
import ArmModel from "./ArmModel";
import RoverModel from "./RoverModel";

/** Advances the simulation clock and publishes it to the UI about ten times a second. */
function PlaybackDriver() {
  const lastPublish = useRef(0);
  useFrame((_, delta) => {
    const st = useStudio.getState();
    if (!st.playing || !st.sim) return;
    clock.time = Math.min(clock.time + Math.min(delta, 0.1) * st.speed, st.sim.data.duration);
    const done = clock.time >= st.sim.data.duration;
    const now = performance.now();
    if (done || now - lastPublish.current > 100) {
      lastPublish.current = now;
      useStudio.setState(done ? { simTime: clock.time, playing: false } : { simTime: clock.time });
    }
  });
  return null;
}

/** Frames the robot (or the simulated path) whenever the view key changes. */
function CameraRig({ template }: { template: TemplateId }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;
  const getThree = useThree((s) => s.get);
  const viewKey = useStudio((s) => s.viewKey);

  useEffect(() => {
    const st = useStudio.getState();
    const d = st.design;
    if (!d || !controls) return;
    let target: THREE.Vector3;
    let distance: number;
    if (d.template === "arm") {
      const arm = d as ArmDesign;
      const reach = arm.upper_arm_length + arm.forearm_length;
      target = new THREE.Vector3(reach * 0.25, arm.base_height * 0.75, 0);
      distance = (reach + arm.base_height) * 2.0;
    } else {
      const rover = d as RoverDesign;
      const sim = st.sim?.kind === "rover" ? st.sim.data : null;
      if (sim) {
        const b = sim.bounds;
        target = new THREE.Vector3((b.min_x + b.max_x) / 2, 0, -(b.min_y + b.max_y) / 2);
        distance = Math.max(b.max_x - b.min_x, b.max_y - b.min_y, rover.chassis_length * 3) * 1.3 + 0.3;
      } else {
        target = new THREE.Vector3(rover.chassis_length * 0.2, 0.03, 0);
        distance = Math.max(rover.chassis_length, rover.track_width) * 4.2;
      }
    }
    // Small (phone) viewports are mostly covered by overlays: back off a little.
    if (getThree().size.height < 520) distance *= 1.3;
    const dir = new THREE.Vector3(1, 0.8, 1.15).normalize();
    camera.position.copy(target).addScaledVector(dir, distance);
    controls.target.copy(target);
    controls.update();
    // Reframe only on explicit requests (view key / template), not on every design tweak.
  }, [viewKey, template, controls, camera, getThree]);

  return (
    <OrbitControls
      makeDefault
      enableDamping
      dampingFactor={0.12}
      maxPolarAngle={Math.PI / 2 - 0.03}
      minDistance={0.08}
      maxDistance={25}
    />
  );
}

function Floor({ template }: { template: TemplateId }) {
  const arm = template === "arm";
  return (
    <>
      <Grid
        infiniteGrid
        cellSize={arm ? 0.02 : 0.1}
        sectionSize={arm ? 0.1 : 0.5}
        cellThickness={0.6}
        sectionThickness={1}
        cellColor="#1a2433"
        sectionColor="#27425a"
        fadeDistance={arm ? 2.2 : 12}
        fadeStrength={1.5}
        position={[0, -0.0005, 0]}
      />
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[40, 40]} />
        <shadowMaterial transparent opacity={0.35} />
      </mesh>
    </>
  );
}

export default function Viewport() {
  const template = useStudio((s) => s.design?.template);
  const shadowSpan = template === "arm" ? 0.7 : 4;
  const lightProps = useMemo(
    () => ({
      "shadow-camera-left": -shadowSpan,
      "shadow-camera-right": shadowSpan,
      "shadow-camera-top": shadowSpan,
      "shadow-camera-bottom": -shadowSpan,
    }),
    [shadowSpan],
  );
  if (!template) return null;
  return (
    <Canvas
      shadows="percentage"
      dpr={[1, 2]}
      camera={{ fov: 38, near: 0.005, far: 80, position: [0.6, 0.45, 0.6] }}
      onPointerMissed={() => useStudio.setState({ focusRole: null })}
    >
      <color attach="background" args={["#070b12"]} />
      <fog attach="fog" args={["#070b12", template === "arm" ? 2.5 : 10, template === "arm" ? 6 : 26]} />
      <ambientLight intensity={0.45} />
      <hemisphereLight args={["#cfeeff", "#1b2433", 0.55]} />
      <directionalLight
        key={template}
        position={template === "arm" ? [0.8, 1.6, 0.9] : [3, 6, 3.5]}
        intensity={1.6}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        {...lightProps}
      />
      <directionalLight position={[-1.5, 1, -1]} intensity={0.35} color="#9ad8ff" />
      <Floor template={template} />
      {template === "arm" ? <ArmModel /> : <RoverModel />}
      <CameraRig template={template} />
      <PlaybackDriver />
    </Canvas>
  );
}
