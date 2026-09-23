"use client";

import { useCallback, useEffect, useRef } from "react";
import { api, isAbort } from "./api";
import { useStudio } from "./store";
import type { Vec3 } from "./types";

/**
 * Runs `fn` with the latest arguments, one call at a time. While a call is in flight, newer
 * arguments replace older pending ones, so dragging never floods the backend or starves it.
 */
export function useLatestRunner<T>(fn: (args: T) => Promise<void>) {
  const state = useRef<{ running: boolean; pending: T | null }>({ running: false, pending: null });
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);
  return useCallback((args: T) => {
    const s = state.current;
    if (s.running) {
      s.pending = args;
      return;
    }
    s.running = true;
    void (async () => {
      let next: T | null = args;
      while (next !== null) {
        s.pending = null;
        try {
          await fnRef.current(next);
        } catch {
          /* errors are reported by fn */
        }
        next = s.pending;
      }
      s.running = false;
    })();
  }, []);
}

/** Mechanical + Electrical analysis, debounced on every design change. */
export function useAnalysis() {
  const design = useStudio((s) => s.design);
  useEffect(() => {
    if (!design) return;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      useStudio.setState({ analyzing: true });
      try {
        const analysis = await api.analyze(design, ctrl.signal);
        useStudio.setState({ analysis, analysisError: null, analyzing: false });
      } catch (err) {
        if (!isAbort(err)) {
          useStudio.setState({ analysisError: (err as Error).message, analyzing: false });
        }
      }
    }, 220);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [design]);
}

/** Forward/inverse kinematics for the arm's interactive pose. */
export function useArmPose() {
  const design = useStudio((s) => s.design);
  const poseMode = useStudio((s) => s.poseMode);
  const target = useStudio((s) => s.target);
  const joints = useStudio((s) => s.joints);
  const massesKey = useStudio((s) =>
    s.analysis?.mechanical.template === "arm"
      ? JSON.stringify(s.analysis.mechanical.actuator_masses_kg)
      : "{}",
  );

  const run = useLatestRunner(
    async (args: { mode: "ik" | "fk"; target: Vec3; joints: Vec3; masses: string }) => {
      const st = useStudio.getState();
      if (st.design?.template !== "arm") return;
      try {
        const pose = await api.armPose({
          design: st.design,
          mode: args.mode,
          target: args.target,
          joints: args.joints,
          current: st.pose?.q_deg,
          actuator_masses_kg: JSON.parse(args.masses),
        });
        useStudio.setState({ pose, actionError: null });
      } catch (err) {
        useStudio.setState({ actionError: (err as Error).message });
      }
    },
  );

  useEffect(() => {
    if (design?.template !== "arm") return;
    run({ mode: poseMode, target, joints, masses: massesKey });
  }, [design, poseMode, target, joints, massesKey, run]);
}

/** Firmware generation, only while the Code tab is open. */
export function useCodegen() {
  const tab = useStudio((s) => s.tab);
  const design = useStudio((s) => s.design);
  const language = useStudio((s) => s.language);
  const preset = useStudio((s) => s.roverPreset);
  useEffect(() => {
    if (tab !== "code" || !design) return;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      useStudio.setState({ codeLoading: true });
      try {
        const code = await api.codegen(design, language, preset, ctrl.signal);
        useStudio.setState({ code, codeError: null, codeLoading: false });
      } catch (err) {
        if (!isAbort(err)) {
          useStudio.setState({ codeError: (err as Error).message, codeLoading: false, code: null });
        }
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [tab, design, language, preset]);
}
