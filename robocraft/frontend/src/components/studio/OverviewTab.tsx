"use client";

import { ChevronDown, Sparkles } from "lucide-react";
import { useState } from "react";
import { mass, mm, usd } from "@/lib/format";
import { useStudio } from "@/lib/store";
import type { ArmDesign, Check, RoverDesign } from "@/lib/types";
import { AutoFixChip, Badge, SectionTitle, Segmented, SeverityIcon, Stat, cx } from "../ui";

const ORDER = { error: 0, warning: 1, info: 2, pass: 3 } as const;

export function CheckRow({ check }: { check: Check }) {
  const [open, setOpen] = useState(check.severity === "error");
  return (
    <li className="rounded-lg border border-ink-800 bg-ink-900/50">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 px-2.5 py-2 text-left"
      >
        <SeverityIcon severity={check.severity} className="mt-px" />
        <span className="flex-1 text-xs leading-snug text-ink-100">{check.title}</span>
        {check.auto_fixed && <AutoFixChip />}
        <ChevronDown
          className={cx("mt-px size-3.5 shrink-0 text-ink-400 transition-transform", !open && "-rotate-90")}
        />
      </button>
      {open && (
        <div className="space-y-1.5 px-2.5 pb-2.5 pl-8 text-[11px] leading-relaxed text-ink-300">
          <p>{check.detail}</p>
          {check.fix && (
            <p className="rounded-md bg-ink-800/70 px-2 py-1.5 text-ink-100">
              <span className="font-semibold text-brand-300">What to do: </span>
              {check.fix}
            </p>
          )}
          <p className="text-ink-400 capitalize">{check.engine} engine</p>
        </div>
      )}
    </li>
  );
}

export default function OverviewTab() {
  const analysis = useStudio((s) => s.analysis);
  const design = useStudio((s) => s.design);
  const [filter, setFilter] = useState<"issues" | "auto" | "all">("all");
  if (!analysis || !design) return null;
  const { summary, mechanical, electrical } = analysis;
  const checks = [...mechanical.checks, ...electrical.checks].sort(
    (a, b) => ORDER[a.severity] - ORDER[b.severity],
  );
  const shown = checks.filter((c) =>
    filter === "all"
      ? true
      : filter === "auto"
        ? c.auto_fixed
        : c.severity === "error" || c.severity === "warning",
  );
  const tone = summary.status === "ok" ? "ok" : summary.status === "warning" ? "warn" : "error";

  return (
    <div className="space-y-5">
      <div
        className={cx(
          "rounded-xl border p-3.5",
          tone === "ok" && "border-emerald-500/30 bg-emerald-500/5",
          tone === "warn" && "border-amber-500/30 bg-amber-500/5",
          tone === "error" && "border-red-500/30 bg-red-500/5",
        )}
      >
        <div className="flex items-center gap-2">
          <SeverityIcon
            severity={summary.status === "ok" ? "pass" : summary.status === "warning" ? "warning" : "error"}
            className="size-5"
          />
          <h2 className="text-sm font-semibold">{summary.headline}</h2>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge tone="ok">{summary.check_counts.pass} passed</Badge>
          {summary.auto_fixes > 0 && (
            <Badge tone="brand">
              <Sparkles className="size-3" /> {summary.auto_fixes} safety fixes applied
            </Badge>
          )}
          {summary.check_counts.warning > 0 && (
            <Badge tone="warn">{summary.check_counts.warning} warnings</Badge>
          )}
          {summary.check_counts.error > 0 && <Badge tone="error">{summary.check_counts.error} errors</Badge>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Stat
          label="Parts cost"
          value={usd(summary.total_cost_usd)}
          hint={`${electrical.bom.length} line items`}
        />
        <Stat label="Total mass" value={mass(summary.total_mass_kg)} />
        {mechanical.template === "arm" ? (
          <>
            <Stat
              label="Max payload"
              value={mass(mechanical.max_payload_kg)}
              hint={`design: ${mass((design as ArmDesign).payload_mass)}`}
              tone={mechanical.max_payload_kg >= (design as ArmDesign).payload_mass ? "ok" : "error"}
            />
            <Stat label="Reach" value={mm(mechanical.reach.max)} hint="from the shoulder axis" />
          </>
        ) : (
          <>
            <Stat
              label="Top speed"
              value={`${(design as RoverDesign).max_speed.toFixed(2)} m/s`}
              hint={`motors allow ≈${mechanical.motor_top_speed_mps.toFixed(2)} m/s`}
              tone={mechanical.motor_top_speed_mps >= (design as RoverDesign).max_speed ? "ok" : "error"}
            />
            <Stat
              label="Runtime"
              value={
                summary.runtime_min != null && Number.isFinite(summary.runtime_min)
                  ? `${Math.round(summary.runtime_min)} min`
                  : "-"
              }
              hint="continuous cruising"
            />
          </>
        )}
      </div>

      <section>
        <SectionTitle
          action={
            <Segmented
              size="sm"
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: `All ${checks.length}` },
                { value: "issues", label: "Issues" },
                { value: "auto", label: "Auto-fixes" },
              ]}
            />
          }
        >
          Design checks
        </SectionTitle>
        {shown.length === 0 ? (
          <p className="rounded-lg border border-dashed border-ink-800 p-3 text-center text-xs text-ink-400">
            Nothing here -{" "}
            {filter === "issues" ? "no warnings or errors." : "no automatic fixes were needed."}
          </p>
        ) : (
          <ul className="space-y-1.5">
            {shown.map((c) => (
              <CheckRow key={`${c.engine}-${c.id}`} check={c} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
