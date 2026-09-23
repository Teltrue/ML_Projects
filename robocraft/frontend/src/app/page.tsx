import { ArrowRight, Bot, Box, Car, CircuitBoard, Code, Gauge, Sparkles } from "lucide-react";
import Link from "next/link";
import Logo from "@/components/Logo";
import SavedProjects from "@/components/SavedProjects";

const ENGINES = [
  {
    icon: Box,
    name: "Spatial Engine",
    text: "A live 3D model you shape with sliders. Drag the gripper target and watch the arm solve its pose.",
  },
  {
    icon: Gauge,
    name: "Mechanical Engine",
    text: "DH parameters, forward and inverse kinematics, worst-case joint torques, centre of mass and traction.",
  },
  {
    icon: CircuitBoard,
    name: "Electrical Engine",
    text: "Picks motors, drivers and batteries for those torques and wires a safe circuit - regulators, level shifters and fuses included.",
  },
  {
    icon: Code,
    name: "Code Generation",
    text: "Ready-to-flash Arduino C++ or MicroPython using the exact pins, geometry and motion from your design.",
  },
];

const TEMPLATES = [
  {
    id: "arm",
    icon: Bot,
    name: "3-Axis Robotic Arm",
    tagline: "Desktop pick-and-place arm with a gripper",
    points: [
      "Closed-form inverse kinematics",
      "Payload-to-torque servo sizing",
      "Tip-over and reach analysis",
      "Separate, protected servo power rail",
    ],
  },
  {
    id: "rover",
    icon: Car,
    name: "Differential-Drive Rover",
    tagline: "2WD or 4WD rover with obstacle avoidance",
    points: [
      "Drive-force budget for slopes and terrain",
      "DC motor + H-bridge (L298N) matching",
      "Battery runtime and 5 V logic rail",
      "Simulated driving with the same ramps as the firmware",
    ],
  },
];

export default function Home() {
  return (
    <div className="rc-grid-bg min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <div className="flex items-center gap-2.5">
          <Logo className="size-8" />
          <span className="text-lg font-semibold tracking-tight">RoboCraft</span>
          <span className="rounded-full border border-ink-700 px-2 py-0.5 text-[10px] text-ink-400">MVP</span>
        </div>
        <Link
          href="/studio/arm"
          className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm hover:border-ink-600"
        >
          Open studio <ArrowRight className="size-4" />
        </Link>
      </header>

      <main className="mx-auto max-w-6xl px-5 pb-20">
        <section className="py-12 sm:py-20">
          <p className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs text-brand-300">
            <Sparkles className="size-3.5" /> The accessible robotics builder
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            Build a real robot without mastering three engineering degrees first.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-pretty text-ink-300">
            Shape your robot in 3D. RoboCraft works out the kinematics and torques, chooses the motors, wires
            a circuit that won&apos;t fry your board, and writes the firmware - so you can focus on what the
            robot should do.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/studio/arm"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-sm font-semibold text-ink-950 hover:bg-brand-400"
            >
              <Bot className="size-4" /> Design a robot arm
            </Link>
            <Link
              href="/studio/rover"
              className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 px-5 py-3 text-sm font-semibold hover:border-ink-600"
            >
              <Car className="size-4" /> Design a rover
            </Link>
          </div>
        </section>

        <section aria-labelledby="engines">
          <h2 id="engines" className="mb-4 text-xs font-semibold tracking-[0.14em] text-ink-400 uppercase">
            Four engines, one pipeline
          </h2>
          <ol className="grid gap-3 md:grid-cols-4">
            {ENGINES.map((e, i) => {
              const Icon = e.icon;
              return (
                <li key={e.name} className="relative rounded-2xl border border-ink-800 bg-ink-900/70 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="flex size-9 items-center justify-center rounded-lg bg-brand-500/10 text-brand-300">
                      <Icon className="size-4.5" />
                    </span>
                    <span className="text-xs text-ink-600 tabular-nums">0{i + 1}</span>
                  </div>
                  <h3 className="text-sm font-semibold">{e.name}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-400">{e.text}</p>
                </li>
              );
            })}
          </ol>
        </section>

        <section aria-labelledby="templates" className="mt-16">
          <h2 id="templates" className="mb-4 text-xs font-semibold tracking-[0.14em] text-ink-400 uppercase">
            Start from a template
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {TEMPLATES.map((t) => {
              const Icon = t.icon;
              return (
                <Link
                  key={t.id}
                  href={`/studio/${t.id}`}
                  className="group rounded-2xl border border-ink-800 bg-ink-900/70 p-6 transition-colors hover:border-brand-500/50"
                >
                  <div className="flex items-start justify-between">
                    <span className="flex size-12 items-center justify-center rounded-xl bg-ink-800 text-brand-300">
                      <Icon className="size-6" />
                    </span>
                    <ArrowRight className="size-5 text-ink-600 transition-transform group-hover:translate-x-1 group-hover:text-brand-300" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">{t.name}</h3>
                  <p className="text-sm text-ink-400">{t.tagline}</p>
                  <ul className="mt-4 space-y-1.5 text-sm text-ink-300">
                    {t.points.map((p) => (
                      <li key={p} className="flex items-center gap-2">
                        <span className="size-1.5 rounded-full bg-brand-400" /> {p}
                      </li>
                    ))}
                  </ul>
                </Link>
              );
            })}
          </div>
        </section>

        <section aria-labelledby="projects" className="mt-16">
          <h2 id="projects" className="mb-4 text-xs font-semibold tracking-[0.14em] text-ink-400 uppercase">
            Your projects
          </h2>
          <SavedProjects />
        </section>

        <footer className="mt-20 border-t border-ink-800 pt-6 text-xs text-ink-400">
          Phase 1 MVP: constrained templates. Next up: a drag-and-drop circuit builder and a freeform sandbox
          with URDF export. Component ratings are typical values - always check the datasheet.
        </footer>
      </main>
    </div>
  );
}
