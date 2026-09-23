"use client";

import { ChevronDown, Info } from "lucide-react";
import { useState } from "react";
import { trimNumber } from "@/lib/format";
import { useStudio } from "@/lib/store";
import type { ParameterSpec } from "@/lib/types";
import { RangeInput, Toggle, cx } from "../ui";

function NumberField({
  value,
  min,
  max,
  step,
  onCommit,
  label,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onCommit: (v: number) => void;
  label: string;
}) {
  const shown = trimNumber(value, step);
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    if (draft === null) return;
    const parsed = Number(draft);
    if (Number.isFinite(parsed)) onCommit(Math.min(Math.max(parsed, min), max));
    setDraft(null);
  };
  return (
    <input
      aria-label={label}
      inputMode="decimal"
      className="w-16 rounded-md border border-transparent bg-transparent px-1 py-0.5 text-right text-xs text-ink-100 tabular-nums hover:border-ink-700 focus:border-brand-500 focus:bg-ink-900 focus:outline-none"
      value={draft ?? shown}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") setDraft(null);
      }}
    />
  );
}

export function ParamSlider({
  label,
  unit,
  value,
  min,
  max,
  step,
  onChange,
  help,
}: {
  label: string;
  unit?: string | null;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  help?: string;
}) {
  return (
    <div className="py-1.5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-xs text-ink-300">
          {label}
          {help && (
            <span title={help} className="text-ink-400">
              <Info className="size-3" />
            </span>
          )}
        </span>
        <span className="flex items-baseline">
          <NumberField label={label} value={value} min={min} max={max} step={step} onCommit={onChange} />
          {unit && <span className="w-9 pl-1 text-[11px] text-ink-400">{unit}</span>}
        </span>
      </div>
      <RangeInput ariaLabel={label} value={value} min={min} max={max} step={step} onChange={onChange} />
    </div>
  );
}

function Parameter({ spec }: { spec: ParameterSpec }) {
  const value = useStudio((s) => (s.design as Record<string, unknown> | null)?.[spec.key]);
  const setParam = useStudio((s) => s.setParam);

  if (spec.kind === "toggle") {
    return <Toggle label={spec.label} checked={Boolean(value)} onChange={(v) => setParam(spec.key, v)} />;
  }
  if (spec.kind === "select") {
    const current = spec.options.find((o) => String(o.value) === String(value));
    return (
      <label className="block py-1.5">
        <span className="mb-1 block text-xs text-ink-300">{spec.label}</span>
        <select
          className="w-full rounded-lg border border-ink-700 bg-ink-900 px-2.5 py-1.5 text-xs text-ink-100 focus:border-brand-500 focus:outline-none"
          value={String(value)}
          onChange={(e) => {
            const opt = spec.options.find((o) => String(o.value) === e.target.value);
            setParam(spec.key, opt ? opt.value : e.target.value);
          }}
        >
          {spec.options.map((o) => (
            <option key={String(o.value)} value={String(o.value)}>
              {o.label}
            </option>
          ))}
        </select>
        {current?.note && <span className="mt-1 block text-[11px] text-ink-400">{current.note}</span>}
      </label>
    );
  }
  const scale = spec.scale || 1;
  return (
    <ParamSlider
      label={spec.label}
      unit={spec.unit}
      help={spec.help}
      value={Number(value) * scale}
      min={(spec.min ?? 0) * scale}
      max={(spec.max ?? 1) * scale}
      step={(spec.step ?? 0.01) * scale}
      onChange={(v) => setParam(spec.key, v / scale)}
    />
  );
}

export function ParamGroup({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border-b border-ink-800 px-4 py-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between text-[11px] font-semibold tracking-[0.12em] text-ink-400 uppercase hover:text-ink-100"
        aria-expanded={open}
      >
        {title}
        <ChevronDown className={cx("size-3.5 transition-transform", !open && "-rotate-90")} />
      </button>
      {open && <div className="mt-2">{children}</div>}
    </section>
  );
}

export default function ParamPanel() {
  const spec = useStudio((s) => s.spec);
  if (!spec) return null;
  return (
    <>
      {spec.groups.map((group) => (
        <ParamGroup key={group} title={group}>
          {spec.parameters
            .filter((p) => p.group === group)
            .map((p) => (
              <Parameter key={p.key} spec={p} />
            ))}
        </ParamGroup>
      ))}
    </>
  );
}
