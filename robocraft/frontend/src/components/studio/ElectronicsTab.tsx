"use client";

import { Download, Maximize2, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { kgcm, pct, usd } from "@/lib/format";
import { useStudio } from "@/lib/store";
import type { Actuator, Electrical } from "@/lib/types";
import { Badge, Button, Card, SectionTitle, UsageBar, cx } from "../ui";
import WiringDiagram, { WiringLegend } from "./WiringDiagram";

const STATUS_TONE = { ok: "ok", marginal: "warn", insufficient: "error" } as const;

function ActuatorCard({ actuator, focused }: { actuator: Actuator; focused: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focused]);
  const rpm = actuator.extra.wheel_rpm;
  return (
    <div
      ref={ref}
      className={cx(
        "rounded-xl border p-3 transition-colors",
        focused ? "border-brand-400 bg-brand-500/5" : "border-ink-800 bg-ink-900/60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] text-ink-400">{actuator.label}</div>
          <div className="text-sm font-medium text-ink-100">{actuator.name}</div>
        </div>
        <Badge tone={STATUS_TONE[actuator.status]}>
          {actuator.status === "ok" ? "good fit" : actuator.status}
        </Badge>
      </div>
      <div className="mt-2">
        <UsageBar
          value={actuator.required_kgcm}
          max={actuator.available_kgcm}
          label={pct(actuator.utilization)}
        />
        <div className="mt-1 flex justify-between text-[11px] text-ink-400 tabular-nums">
          <span>
            needs {kgcm(actuator.required_kgcm)}
            {rpm !== undefined && ` @ ${Math.round(Number(rpm))} RPM`}
          </span>
          <span>has {kgcm(actuator.available_kgcm)}</span>
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-ink-300">{actuator.rationale}</p>
      {actuator.alternatives.length > 0 && (
        <div className="mt-2 border-t border-ink-800 pt-2">
          <div className="mb-1 text-[11px] text-ink-400">Alternatives</div>
          <ul className="space-y-0.5 text-[11px] text-ink-300">
            {actuator.alternatives.map((a) => (
              <li key={a.component_id} className="flex justify-between gap-2">
                <span>{a.name}</span>
                <span className="shrink-0 text-ink-400">
                  {a.rating} · {usd(a.price_usd)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function bomCsv(elec: Electrical) {
  const rows = [["Qty", "Part", "Refs", "Unit USD", "Total USD", "Why", "Auto-added"]];
  for (const b of elec.bom) {
    rows.push([
      String(b.qty),
      b.name,
      b.refs.join(" "),
      b.unit_price_usd.toFixed(2),
      b.total_usd.toFixed(2),
      b.reason + (b.note ? ` (${b.note})` : ""),
      b.auto_added ? "yes" : "",
    ]);
  }
  return rows.map((r) => r.map((c) => `"${c.replaceAll('"', '""')}"`).join(",")).join("\n");
}

export function download(filename: string, content: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function DiagramModal({ elec, onClose }: { elec: Electrical; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const refs = Object.fromEntries(elec.parts.map((p) => [p.ref, p]));
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-ink-950/95 p-4 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-label="Wiring diagram"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Wiring diagram</h2>
          <WiringLegend />
        </div>
        <Button onClick={onClose} aria-label="Close">
          <X className="size-4" /> Close
        </Button>
      </div>
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1fr_340px]">
        <div className="rc-scroll min-h-0 overflow-auto rounded-xl border border-ink-800 bg-ink-900/40">
          <WiringDiagram parts={elec.parts} wires={elec.wires} className="h-auto w-full min-w-[720px]" />
        </div>
        <div className="rc-scroll min-h-0 overflow-auto rounded-xl border border-ink-800 bg-ink-900/40 p-3">
          <SectionTitle>Connections ({elec.wires.length})</SectionTitle>
          <table className="w-full text-[11px]">
            <tbody>
              {elec.wires.map((w, i) => (
                <tr key={i} className="border-t border-ink-800 align-top text-ink-300">
                  <td className="py-1 pr-2">
                    {refs[w.a]?.label} <span className="font-mono text-ink-100">{w.a_pin}</span>
                  </td>
                  <td className="py-1 pr-2 text-ink-400">→</td>
                  <td className="py-1 pr-2">
                    {refs[w.b]?.label} <span className="font-mono text-ink-100">{w.b_pin}</span>
                  </td>
                  <td className="py-1 text-right font-mono text-ink-400">{w.net}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function ElectronicsTab() {
  const analysis = useStudio((s) => s.analysis);
  const focusRole = useStudio((s) => s.focusRole);
  const [expanded, setExpanded] = useState(false);
  if (!analysis) return null;
  const elec = analysis.electrical;
  const autoAdded = elec.bom.filter((b) => b.auto_added).length;

  return (
    <div className="space-y-5">
      <section>
        <SectionTitle>Actuators</SectionTitle>
        <div className="space-y-2">
          {elec.actuators.map((a) => (
            <ActuatorCard key={a.role} actuator={a} focused={focusRole === a.role} />
          ))}
        </div>
      </section>

      <section>
        <SectionTitle
          action={
            <Button size="sm" variant="ghost" onClick={() => setExpanded(true)}>
              <Maximize2 className="size-3" /> Expand
            </Button>
          }
        >
          Wiring diagram
        </SectionTitle>
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="block w-full overflow-hidden rounded-xl border border-ink-800 bg-ink-900/40 transition-colors hover:border-ink-600"
          aria-label="Open the wiring diagram full screen"
        >
          <WiringDiagram parts={elec.parts} wires={elec.wires} className="h-auto w-full" />
        </button>
        <div className="mt-2">
          <WiringLegend />
        </div>
        {expanded && <DiagramModal elec={elec} onClose={() => setExpanded(false)} />}
      </section>

      <section>
        <SectionTitle>Power rails</SectionTitle>
        <div className="space-y-2">
          {elec.rails.map((r) => (
            <Card key={r.name} className="p-2.5">
              <div className="flex items-baseline justify-between text-xs">
                <span className="font-medium text-ink-100">
                  {r.name} · {r.voltage.toFixed(1)} V
                </span>
                <span className="text-ink-400">{r.source}</span>
              </div>
              <div className="mt-1.5">
                <UsageBar value={r.peak_a} max={r.capacity_a} />
              </div>
              <div className="mt-1 flex justify-between text-[11px] text-ink-400 tabular-nums">
                <span>
                  typ {r.typical_a.toFixed(2)} A · peak {r.peak_a.toFixed(2)} A
                </span>
                <span>capacity {r.capacity_a.toFixed(1)} A</span>
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle>Pin assignments · {elec.board.name}</SectionTitle>
        <div className="grid grid-cols-2 gap-1.5">
          {Object.entries(elec.pin_labels).map(([signal, pin]) => (
            <div
              key={signal}
              className="flex items-center justify-between rounded-md border border-ink-800 bg-ink-900/60 px-2 py-1 text-[11px]"
            >
              <span className="text-ink-300">{signal.replace("servo_", "servo ").toUpperCase()}</span>
              <span className="font-mono text-brand-300">{pin}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle
          action={
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                download(`${analysis.name.replace(/\s+/g, "_")}_bom.csv`, bomCsv(elec), "text/csv")
              }
            >
              <Download className="size-3" /> CSV
            </Button>
          }
        >
          Bill of materials
        </SectionTitle>
        <div className="overflow-hidden rounded-xl border border-ink-800">
          <table className="w-full text-xs">
            <tbody>
              {elec.bom.map((b) => (
                <tr key={b.component_id} className="border-b border-ink-800 align-top last:border-0">
                  <td className="w-8 px-2 py-2 text-right text-ink-400 tabular-nums">{b.qty}×</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap items-center gap-1.5 text-ink-100">
                      {b.name}
                      {b.auto_added && (
                        <Badge tone="brand">
                          <Sparkles className="size-3" /> added for safety
                        </Badge>
                      )}
                    </div>
                    <div className="mt-0.5 text-[11px] text-ink-400">{b.reason}</div>
                    {b.note && <div className="mt-0.5 text-[11px] text-amber-200">{b.note}</div>}
                  </td>
                  <td className="px-2 py-2 text-right text-ink-300 tabular-nums">{usd(b.total_usd)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-ink-850">
              <tr>
                <td />
                <td className="px-2 py-2 text-xs text-ink-300">
                  Total{autoAdded > 0 && ` · ${autoAdded} safety parts included`}
                </td>
                <td className="px-2 py-2 text-right text-sm font-semibold tabular-nums">
                  {usd(elec.total_cost_usd)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        <p className="mt-2 text-[11px] text-ink-400">
          Prices and ratings are typical hobby-market values - confirm against the datasheet of the exact part
          you buy.
        </p>
      </section>
    </div>
  );
}
