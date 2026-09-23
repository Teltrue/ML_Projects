"use client";

import { Eye, LoaderCircle, Pause, Play, Ruler, RotateCcw, Scan, X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { clock } from "@/lib/playback";
import { useStudio } from "@/lib/store";
import type { RoverPreset } from "@/lib/types";
import { Button, Segmented, cx } from "../ui";

const PRESETS: { value: RoverPreset; label: string }[] = [
  { value: "square", label: "Square" },
  { value: "figure8", label: "Figure-8" },
  { value: "spin", label: "Spin" },
];

async function runSimulation(preset?: RoverPreset) {
  const st = useStudio.getState();
  if (!st.design) return;
  // Only the latest request may land: a newer click or any design edit bumps the token.
  const request = st.simRequest + 1;
  useStudio.setState({ simLoading: true, simRequest: request });
  const current = () => useStudio.getState().simRequest === request;
  try {
    const sim =
      st.design.template === "arm"
        ? ({ kind: "arm", data: await api.armTrajectory(st.design) } as const)
        : ({ kind: "rover", data: await api.roverSimulate(st.design, preset ?? st.roverPreset) } as const);
    if (current()) {
      useStudio.getState().setSim(sim);
      useStudio.setState({ actionError: null });
    }
  } catch (err) {
    if (current()) useStudio.setState({ actionError: (err as Error).message });
  } finally {
    if (current()) useStudio.setState({ simLoading: false });
  }
}

function PhaseLabel() {
  const sim = useStudio((s) => s.sim);
  const time = useStudio((s) => s.simTime);
  if (!sim) return null;
  if (sim.kind === "arm") {
    const upcoming = sim.data.waypoints.find((w) => w.t >= time - 1e-6);
    return <span className="text-ink-300">→ {upcoming?.label ?? "done"}</span>;
  }
  let t = 0;
  let label = "done";
  for (const step of sim.data.steps) {
    t += step.duration;
    if (time < t) {
      label = step.label;
      break;
    }
  }
  const idx = Math.min(
    sim.data.samples.length - 1,
    Math.max(0, Math.round((time / sim.data.duration) * (sim.data.samples.length - 1))),
  );
  const s = sim.data.samples[idx];
  return (
    <span className="text-ink-300 tabular-nums">
      {label} · {s.v.toFixed(2)} m/s · {((s.omega * 180) / Math.PI).toFixed(0)}°/s
    </span>
  );
}

export function PlaybackBar() {
  const template = useStudio((s) => s.design?.template);
  const sim = useStudio((s) => s.sim);
  const playing = useStudio((s) => s.playing);
  const simTime = useStudio((s) => s.simTime);
  const speed = useStudio((s) => s.speed);
  const loading = useStudio((s) => s.simLoading);
  const preset = useStudio((s) => s.roverPreset);
  const setSim = useStudio((s) => s.setSim);
  if (!template) return null;
  const duration = sim?.data.duration ?? 0;

  const togglePlay = () => {
    if (playing) useStudio.setState({ playing: false });
    else {
      if (clock.time >= duration) clock.time = 0;
      useStudio.setState({ playing: true, simTime: clock.time });
    }
  };

  return (
    <div className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-xl border border-ink-800 bg-ink-900/85 p-2 shadow-lg backdrop-blur">
      {template === "rover" && (
        <Segmented
          size="sm"
          value={preset}
          options={PRESETS}
          onChange={(p) => {
            useStudio.setState({ roverPreset: p });
            if (sim) void runSimulation(p);
          }}
        />
      )}
      {!sim ? (
        <Button variant="primary" size="sm" onClick={() => runSimulation()} disabled={loading}>
          {loading ? <LoaderCircle className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
          {template === "arm" ? "Simulate pick & place" : "Simulate drive"}
        </Button>
      ) : (
        <>
          <Button size="sm" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
            {playing ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
          </Button>
          <input
            type="range"
            aria-label="Timeline"
            className="rc-range min-w-24 flex-1"
            min={0}
            max={duration}
            step={0.01}
            value={simTime}
            style={{ "--fill": `${(simTime / duration) * 100}%` } as React.CSSProperties}
            onChange={(e) => {
              clock.time = Number(e.target.value);
              useStudio.setState({ simTime: clock.time, playing: false });
            }}
          />
          <span className="w-20 text-right text-[11px] text-ink-300 tabular-nums">
            {simTime.toFixed(1)} / {duration.toFixed(1)} s
          </span>
          <Segmented
            size="sm"
            value={String(speed)}
            options={[
              { value: "0.5", label: "½×" },
              { value: "1", label: "1×" },
              { value: "2", label: "2×" },
            ]}
            onChange={(v) => useStudio.setState({ speed: Number(v) })}
          />
          <Button size="sm" variant="ghost" onClick={() => setSim(null)} aria-label="Exit simulation">
            <X className="size-3.5" />
          </Button>
        </>
      )}
      {sim && (
        <div className="basis-full px-1 text-[11px]">
          <PhaseLabel />
        </div>
      )}
    </div>
  );
}

export function ViewToggles() {
  const template = useStudio((s) => s.design?.template);
  const showDimensions = useStudio((s) => s.showDimensions);
  const showReach = useStudio((s) => s.showReach);
  const resetView = useStudio((s) => s.resetView);
  const [hint, setHint] = useState(true);
  const chip = (active: boolean) =>
    cx(
      "inline-flex h-7 items-center gap-1 rounded-lg border px-2 text-[11px] transition-colors",
      active
        ? "border-brand-500/40 bg-brand-500/15 text-brand-300"
        : "border-ink-800 bg-ink-900/80 text-ink-400 hover:text-ink-100",
    );
  return (
    <div className="pointer-events-auto flex flex-col items-end gap-2">
      <div className="flex gap-1.5">
        <button
          type="button"
          className={chip(showDimensions)}
          onClick={() => useStudio.setState({ showDimensions: !showDimensions })}
        >
          <Ruler className="size-3" /> Dimensions
        </button>
        {template === "arm" && (
          <button
            type="button"
            className={chip(showReach)}
            onClick={() => useStudio.setState({ showReach: !showReach })}
          >
            <Scan className="size-3" /> Reach
          </button>
        )}
        <button type="button" className={chip(false)} onClick={resetView} aria-label="Reset view">
          <RotateCcw className="size-3" />
        </button>
      </div>
      {hint && (
        <button
          type="button"
          onClick={() => setHint(false)}
          className="flex max-w-60 items-start gap-1.5 rounded-lg border border-ink-800 bg-ink-900/80 px-2 py-1.5 text-left text-[11px] text-ink-400 max-sm:hidden"
        >
          <Eye className="mt-px size-3 shrink-0" />
          {template === "arm"
            ? "Drag to orbit, scroll to zoom. Drag the target's arrows to move the gripper; click a servo for details."
            : "Drag to orbit, scroll to zoom. Click a motor for details, then simulate a drive."}
        </button>
      )}
    </div>
  );
}
