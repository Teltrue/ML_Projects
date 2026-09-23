"use client";

import { CircuitBoard, Code, Gauge, LayoutDashboard, LoaderCircle, TriangleAlert } from "lucide-react";
import { useStudio, type InsightTab } from "@/lib/store";
import { cx } from "../ui";
import CodeTab from "./CodeTab";
import ElectronicsTab from "./ElectronicsTab";
import MechanicsTab from "./MechanicsTab";
import OverviewTab from "./OverviewTab";

const TABS: { id: InsightTab; label: string; icon: typeof Gauge }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "mechanics", label: "Mechanics", icon: Gauge },
  { id: "electronics", label: "Electronics", icon: CircuitBoard },
  { id: "code", label: "Code", icon: Code },
];

export default function Insights() {
  const tab = useStudio((s) => s.tab);
  const analysis = useStudio((s) => s.analysis);
  const analyzing = useStudio((s) => s.analyzing);
  const error = useStudio((s) => s.analysisError);
  const counts = analysis?.summary.check_counts;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        className="rc-scroll flex items-center gap-1 overflow-x-auto border-b border-ink-800 px-2 pt-2"
        role="tablist"
      >
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => useStudio.setState({ tab: t.id })}
              className={cx(
                "relative flex shrink-0 items-center gap-1.5 rounded-t-lg px-2.5 py-2 text-xs font-medium whitespace-nowrap transition-colors sm:px-3",
                active ? "bg-ink-900 text-ink-100" : "text-ink-400 hover:text-ink-100",
              )}
            >
              <Icon className="size-3.5" />
              {t.label}
              {t.id === "overview" && counts && counts.error + counts.warning > 0 && (
                <span
                  className={cx(
                    "ml-0.5 rounded-full px-1.5 text-[10px]",
                    counts.error ? "bg-red-500/20 text-red-300" : "bg-amber-500/20 text-amber-300",
                  )}
                >
                  {counts.error + counts.warning}
                </span>
              )}
              {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-brand-400" />}
            </button>
          );
        })}
        <div className="ml-auto pr-2">
          {analyzing && <LoaderCircle className="size-4 animate-spin text-ink-400" aria-label="Analysing" />}
        </div>
      </div>
      <div className="rc-scroll min-h-0 flex-1 overflow-y-auto p-4">
        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-200">
            <TriangleAlert className="mt-px size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {!analysis && !error ? (
          <div className="flex h-40 items-center justify-center gap-2 text-sm text-ink-400">
            <LoaderCircle className="size-4 animate-spin" /> Running the engines…
          </div>
        ) : (
          <div role="tabpanel">
            {tab === "overview" && <OverviewTab />}
            {tab === "mechanics" && <MechanicsTab />}
            {tab === "electronics" && <ElectronicsTab />}
            {tab === "code" && <CodeTab />}
          </div>
        )}
      </div>
    </div>
  );
}
