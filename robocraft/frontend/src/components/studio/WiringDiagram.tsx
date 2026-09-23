"use client";

import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import type { Part, Wire } from "@/lib/types";

const BOX_W = 172;
const HEADER_H = 42;
const PIN_H = 17;
const COL_GAP = 118;
const ROW_GAP = 22;
const PAD = 26;

const POWER_COLORS: Record<string, string> = {
  VBAT: "#ef4444",
  V_SERVO: "#f43f5e",
  "5V": "#f97316",
  USB_5V: "#fb923c",
  VLOGIC: "#eab308",
};
const SIGNAL_COLORS = [
  "#38bdf8",
  "#a78bfa",
  "#34d399",
  "#facc15",
  "#f472b6",
  "#22d3ee",
  "#c084fc",
  "#4ade80",
  "#60a5fa",
];

export function wireColor(wire: Wire, signalIndex: Map<string, number>) {
  if (wire.kind === "ground") return "#64748b";
  if (wire.kind === "power") return POWER_COLORS[wire.net] ?? "#ef4444";
  if (wire.kind === "motor") return wire.net.endsWith("_A") ? "#d946ef" : "#8b5cf6";
  return SIGNAL_COLORS[(signalIndex.get(wire.net) ?? 0) % SIGNAL_COLORS.length];
}

interface Box {
  part: Part;
  x: number;
  y: number;
  h: number;
  col: number;
}

function layout(parts: Part[], wires: Wire[]) {
  const visible = parts.filter((p) => p.in_diagram);
  const columns = [...new Set(visible.map((p) => p.column))].sort((a, b) => a - b);
  const colOf = new Map(columns.map((c, i) => [c, i]));
  const byCol: Part[][] = columns.map((c) => visible.filter((p) => p.column === c));
  const neighbours = new Map<string, string[]>();
  for (const w of wires) {
    neighbours.set(w.a, [...(neighbours.get(w.a) ?? []), w.b]);
    neighbours.set(w.b, [...(neighbours.get(w.b) ?? []), w.a]);
  }
  const height = (p: Part) => HEADER_H + p.pins.length * PIN_H + 8;

  const place = () => {
    const boxes = new Map<string, Box>();
    const colHeights = byCol.map((list) => list.reduce((acc, p) => acc + height(p) + ROW_GAP, -ROW_GAP));
    const maxH = Math.max(...colHeights, 0);
    byCol.forEach((list, ci) => {
      let y = PAD + (maxH - colHeights[ci]) / 2;
      for (const p of list) {
        boxes.set(p.ref, { part: p, x: PAD + ci * (BOX_W + COL_GAP), y, h: height(p), col: ci });
        y += height(p) + ROW_GAP;
      }
    });
    return { boxes, maxH };
  };

  // Two barycentre sweeps to reduce wire crossings.
  let placed = place();
  for (let sweep = 0; sweep < 2; sweep++) {
    byCol.forEach((list, ci) => {
      const centre = (p: Part) => {
        const ys = (neighbours.get(p.ref) ?? [])
          .map((ref) => placed.boxes.get(ref))
          .filter((b): b is Box => !!b && b.col !== ci)
          .map((b) => b.y + b.h / 2);
        return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : placed.boxes.get(p.ref)!.y;
      };
      const keyed = list.map((p) => [centre(p), p] as const);
      keyed.sort((a, b) => a[0] - b[0]);
      byCol[ci] = keyed.map(([, p]) => p);
    });
    placed = place();
  }
  const width = PAD * 2 + columns.length * BOX_W + Math.max(columns.length - 1, 0) * COL_GAP;
  return { boxes: placed.boxes, width, height: placed.maxH + PAD * 2, colOf };
}

function pinY(box: Box, pin: string) {
  return box.y + HEADER_H + box.part.pins.indexOf(pin) * PIN_H + PIN_H / 2;
}

/** Bezier path for every wire. Pure, so it can be memoised. */
function routeWires(boxes: Map<string, Box>, wires: Wire[], height: number) {
  // Wires that skip a column would pass behind its boxes; they run through a channel above
  // or below those boxes instead, stacked like a bus.
  let above = 0;
  let below = 0;
  let minY = 0;
  let maxY = height;
  const paths = wires.flatMap((w, i) => {
    const a = boxes.get(w.a);
    const b = boxes.get(w.b);
    if (!a || !b) return [];
    const y1 = pinY(a, w.a_pin);
    const y2 = pinY(b, w.b_pin);
    let d: string;
    if (a.col === b.col) {
      const x = a.x + BOX_W;
      const bulge = 40 + Math.abs(y2 - y1) * 0.15;
      d = `M${x},${y1} C${x + bulge},${y1} ${x + bulge},${y2} ${x},${y2}`;
    } else {
      const [l, r, yl, yr] = a.x < b.x ? [a, b, y1, y2] : [b, a, y2, y1];
      const x1 = l.x + BOX_W;
      const x2 = r.x;
      const blockers = [...boxes.values()].filter((bx) => bx.col > l.col && bx.col < r.col);
      const lo = Math.min(yl, yr) - 6;
      const hi = Math.max(yl, yr) + 6;
      if (blockers.some((bx) => bx.y < hi && bx.y + bx.h > lo)) {
        const top = Math.min(...blockers.map((bx) => bx.y));
        const bottom = Math.max(...blockers.map((bx) => bx.y + bx.h));
        const mid = (yl + yr) / 2;
        const yc = mid - top < bottom - mid ? top - 14 - 7 * above++ : bottom + 14 + 7 * below++;
        minY = Math.min(minY, yc - 10);
        maxY = Math.max(maxY, yc + 10);
        const g = COL_GAP * 0.5;
        d =
          `M${x1},${yl} C${x1 + g * 0.6},${yl} ${x1 + g * 0.4},${yc} ${x1 + g},${yc} ` +
          `L${x2 - g},${yc} C${x2 - g * 0.4},${yc} ${x2 - g * 0.6},${yr} ${x2},${yr}`;
      } else {
        const dx = Math.max(36, (x2 - x1) * 0.45);
        d = `M${x1},${yl} C${x1 + dx},${yl} ${x2 - dx},${yr} ${x2},${yr}`;
      }
    }
    return [{ key: `${i}`, d, wire: w }];
  });
  const viewTop = Math.min(0, minY);
  const viewHeight = Math.max(height, maxY) - viewTop;
  return { paths, viewTop, viewHeight };
}

export default function WiringDiagram({
  parts,
  wires,
  className,
}: {
  parts: Part[];
  wires: Wire[];
  className?: string;
}) {
  const [hoverNet, setHoverNet] = useState<string | null>(null);
  const { boxes, width, height } = useMemo(() => layout(parts, wires), [parts, wires]);
  const signalIndex = useMemo(() => {
    const nets = [...new Set(wires.filter((w) => w.kind === "signal").map((w) => w.net))];
    return new Map(nets.map((n, i) => [n, i]));
  }, [wires]);

  const {
    paths: routed,
    viewTop,
    viewHeight,
  } = useMemo(() => routeWires(boxes, wires, height), [boxes, wires, height]);
  const paths = routed.map((p) => ({ ...p, color: wireColor(p.wire, signalIndex) }));

  // Draw ground and power first so signals stay on top.
  const rank = { ground: 0, power: 1, motor: 2, signal: 3 };
  paths.sort((p, q) => rank[p.wire.kind] - rank[q.wire.kind]);

  const endpoints = new Map<string, Set<"l" | "r">>();
  for (const { wire } of paths) {
    const a = boxes.get(wire.a)!;
    const b = boxes.get(wire.b)!;
    const sideA = a.col === b.col || a.x < b.x ? "r" : "l";
    const sideB = a.col === b.col ? "r" : b.x < a.x ? "r" : "l";
    const ka = `${wire.a}:${wire.a_pin}`;
    const kb = `${wire.b}:${wire.b_pin}`;
    endpoints.set(ka, (endpoints.get(ka) ?? new Set()).add(sideA));
    endpoints.set(kb, (endpoints.get(kb) ?? new Set()).add(sideB));
  }
  const netOfPin = new Map<string, string>();
  for (const w of wires) {
    netOfPin.set(`${w.a}:${w.a_pin}`, w.net);
    netOfPin.set(`${w.b}:${w.b_pin}`, w.net);
  }

  return (
    <svg
      viewBox={`0 ${viewTop} ${width} ${viewHeight}`}
      className={className}
      role="img"
      aria-label="Wiring diagram"
      onMouseLeave={() => setHoverNet(null)}
    >
      <defs>
        <pattern id="rc-dots" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" fill="#1a2433" />
        </pattern>
      </defs>
      <rect y={viewTop} width={width} height={viewHeight} fill="url(#rc-dots)" />
      {paths.map(({ key, d, wire, color }) => {
        const dim = hoverNet !== null && hoverNet !== wire.net;
        const hot = hoverNet === wire.net;
        return (
          <g key={key} onMouseEnter={() => setHoverNet(wire.net)} style={{ cursor: "pointer" }}>
            <path d={d} stroke="transparent" strokeWidth={10} fill="none" />
            <path
              d={d}
              stroke={color}
              strokeWidth={hot ? 3 : 1.8}
              strokeOpacity={dim ? 0.12 : 0.95}
              strokeDasharray={wire.kind === "ground" ? "5 3" : undefined}
              fill="none"
            >
              <title>{`${wire.net}: ${wire.a}.${wire.a_pin} → ${wire.b}.${wire.b_pin}`}</title>
            </path>
          </g>
        );
      })}
      {[...boxes.values()].map((box) => {
        const p = box.part;
        return (
          <g key={p.ref}>
            <rect
              x={box.x}
              y={box.y}
              width={BOX_W}
              height={box.h}
              rx={9}
              fill="#0f1622"
              stroke={p.auto_added ? "#3dd6ec" : "#2b3a50"}
              strokeDasharray={p.auto_added ? "4 3" : undefined}
              strokeWidth={1.2}
            >
              <title>{`${p.ref} · ${p.name}\n${p.reason}`}</title>
            </rect>
            <text x={box.x + 10} y={box.y + 17} fill="#e6ebf3" fontSize={11.5} fontWeight={600}>
              {p.label.length > 22 ? `${p.label.slice(0, 21)}…` : p.label}
            </text>
            <text x={box.x + BOX_W - 10} y={box.y + 17} fill="#7d8ba3" fontSize={10} textAnchor="end">
              {p.ref}
            </text>
            <text x={box.x + 10} y={box.y + 31} fill="#7d8ba3" fontSize={9}>
              {p.name.length > 30 ? `${p.name.slice(0, 29)}…` : p.name}
            </text>
            {p.auto_added && (
              <g transform={`translate(${box.x + BOX_W - 50}, ${box.y - 8})`}>
                <rect width={44} height={15} rx={7.5} fill="#0e3a44" stroke="#3dd6ec" strokeWidth={0.8} />
                <text x={22} y={10.5} fontSize={8.5} fill="#7ee8f5" textAnchor="middle">
                  auto
                </text>
              </g>
            )}
            {p.pins.map((pin) => {
              const y = pinY(box, pin);
              const sides = endpoints.get(`${p.ref}:${pin}`) ?? new Set();
              const net = netOfPin.get(`${p.ref}:${pin}`);
              const hot = net !== undefined && hoverNet === net;
              return (
                <g key={pin} onMouseEnter={() => net && setHoverNet(net)} style={{ cursor: "pointer" }}>
                  <rect
                    x={box.x + 4}
                    y={y - PIN_H / 2 + 1}
                    width={BOX_W - 8}
                    height={PIN_H - 2}
                    rx={4}
                    fill={hot ? "#172131" : "transparent"}
                  />
                  <text
                    x={box.x + BOX_W / 2}
                    y={y + 3.5}
                    fontSize={10}
                    fill={hot ? "#e6ebf3" : "#a8b3c7"}
                    textAnchor="middle"
                    fontFamily="var(--font-geist-mono), monospace"
                  >
                    {pin}
                  </text>
                  {sides.has("l") && <circle cx={box.x} cy={y} r={3} fill="#a8b3c7" />}
                  {sides.has("r") && <circle cx={box.x + BOX_W} cy={y} r={3} fill="#a8b3c7" />}
                </g>
              );
            })}
          </g>
        );
      })}
      {hoverNet && (
        <g transform={`translate(${PAD}, ${viewTop + viewHeight - 10})`}>
          <text fontSize={11} fill="#e6ebf3">
            Net: {hoverNet}
          </text>
        </g>
      )}
    </svg>
  );
}

export function WiringLegend() {
  const items = [
    { label: "Power", color: "#ef4444" },
    { label: "Ground", color: "#64748b", dashed: true },
    { label: "Signal", color: "#38bdf8" },
    { label: "Motor", color: "#d946ef" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-400">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <svg width="18" height="4" aria-hidden>
            <line
              x1="0"
              y1="2"
              x2="18"
              y2="2"
              stroke={i.color}
              strokeWidth="2"
              strokeDasharray={i.dashed ? "4 2" : undefined}
            />
          </svg>
          {i.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <Sparkles className="size-3 text-brand-300" /> dashed box = added by RoboCraft
      </span>
    </div>
  );
}
