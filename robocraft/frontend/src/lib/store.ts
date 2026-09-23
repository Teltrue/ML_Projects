import { create } from "zustand";
import type {
  Analysis,
  ArmDesign,
  ArmPose,
  ArmTrajectory,
  CodegenResult,
  Design,
  Language,
  RoverPreset,
  RoverSim,
  TemplateSpec,
  Vec3,
} from "./types";

export type InsightTab = "overview" | "mechanics" | "electronics" | "code";

export type Simulation = { kind: "arm"; data: ArmTrajectory } | { kind: "rover"; data: RoverSim };

interface StudioState {
  spec: TemplateSpec | null;
  design: Design | null;
  projectId: string | null;
  savedSnapshot: string | null;

  analysis: Analysis | null;
  analyzing: boolean;
  analysisError: string | null;

  // Arm posing (the IK target can be dragged in the viewport)
  poseMode: "ik" | "fk";
  target: Vec3;
  joints: Vec3;
  gripperClosed: boolean;
  pose: ArmPose | null;
  dragging: boolean;

  // Motion playback
  sim: Simulation | null;
  simLoading: boolean;
  playing: boolean;
  simTime: number;
  speed: number;
  roverPreset: RoverPreset;

  // Panels
  tab: InsightTab;
  focusRole: string | null;
  language: Language;
  code: CodegenResult | null;
  codeLoading: boolean;
  codeError: string | null;
  showDimensions: boolean;
  showReach: boolean;
  viewKey: number;

  init: (spec: TemplateSpec, design: Design, projectId: string | null) => void;
  setParam: (key: string, value: unknown) => void;
  setName: (name: string) => void;
  markSaved: (projectId: string) => void;
  set: (partial: Partial<StudioState>) => void;
  setTarget: (target: Vec3) => void;
  setJoints: (joints: Vec3) => void;
  setPoseMode: (mode: "ik" | "fk") => void;
  setSim: (sim: Simulation | null) => void;
  focusActuator: (role: string) => void;
  resetView: () => void;
}

export const homeTarget = (d: ArmDesign): Vec3 => [d.forearm_length, 0, d.base_height + d.upper_arm_length];

const snapshot = (design: Design) => JSON.stringify(design);

export const useStudio = create<StudioState>((set, get) => ({
  spec: null,
  design: null,
  projectId: null,
  savedSnapshot: null,
  analysis: null,
  analyzing: false,
  analysisError: null,
  poseMode: "ik",
  target: [0.12, 0, 0.22],
  joints: [0, 90, -90],
  gripperClosed: false,
  pose: null,
  dragging: false,
  sim: null,
  simLoading: false,
  playing: false,
  simTime: 0,
  speed: 1,
  roverPreset: "square",
  tab: "overview",
  focusRole: null,
  language: "arduino",
  code: null,
  codeLoading: false,
  codeError: null,
  showDimensions: true,
  showReach: true,
  viewKey: 0,

  init: (spec, design, projectId) =>
    set({
      spec,
      design,
      projectId,
      savedSnapshot: projectId ? snapshot(design) : null,
      analysis: null,
      analysisError: null,
      pose: null,
      sim: null,
      playing: false,
      simTime: 0,
      code: null,
      codeError: null,
      tab: "overview",
      poseMode: "ik",
      target: design.template === "arm" ? homeTarget(design) : [0, 0, 0],
      joints: [0, 90, -90],
      gripperClosed: false,
      language: "arduino",
      viewKey: get().viewKey + 1,
    }),

  setParam: (key, value) => {
    const { design, sim } = get();
    if (!design) return;
    const next = { ...design, [key]: value } as Design;
    // Motion previews are stale once the geometry or limits change.
    set({ design: next, ...(sim ? { sim: null, playing: false, simTime: 0 } : {}) });
    if (next.board !== design.board) {
      const spec = get().spec;
      const board = spec?.parameters
        .find((p) => p.key === "board")
        ?.options.find((o) => o.value === next.board);
      if (board && !String(board.note ?? "").includes("micropython")) set({ language: "arduino" });
    }
  },

  setName: (name) => {
    const { design } = get();
    if (design) set({ design: { ...design, name } });
  },

  markSaved: (projectId) => {
    const { design } = get();
    if (design) set({ projectId, savedSnapshot: snapshot(design) });
  },

  set: (partial) => set(partial),

  setTarget: (target) => set({ target, poseMode: "ik" }),

  setJoints: (joints) => set({ joints, poseMode: "fk" }),

  setPoseMode: (mode) => {
    const { pose } = get();
    if (mode === "ik" && pose) set({ poseMode: mode, target: pose.ee });
    else if (mode === "fk" && pose) set({ poseMode: mode, joints: pose.q_deg });
    else set({ poseMode: mode });
  },

  setSim: (sim) =>
    set((s) => ({
      sim,
      simTime: 0,
      playing: sim !== null,
      // Re-frame the camera around a rover's path (and back when leaving the simulation).
      viewKey: sim?.kind === "rover" || s.sim?.kind === "rover" ? s.viewKey + 1 : s.viewKey,
    })),

  focusActuator: (role) => set({ tab: "electronics", focusRole: role }),

  resetView: () => set((s) => ({ viewKey: s.viewKey + 1 })),
}));

export const isDirty = (s: Pick<StudioState, "design" | "savedSnapshot">) =>
  !!s.design && s.savedSnapshot !== snapshot(s.design);
