"use client";

import { CircleCheck, CircleX, Info, Sparkles, TriangleAlert } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Severity } from "@/lib/types";

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        variant === "primary" && "bg-brand-500 text-ink-950 hover:bg-brand-400",
        variant === "secondary" &&
          "border border-ink-700 bg-ink-850 text-ink-100 hover:border-ink-600 hover:bg-ink-800",
        variant === "ghost" && "text-ink-300 hover:bg-ink-800 hover:text-ink-100",
        variant === "danger" && "text-red-300 hover:bg-red-500/10",
        className,
      )}
    />
  );
}

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: "neutral" | "ok" | "warn" | "error" | "brand" | "info";
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap",
        tone === "neutral" && "bg-ink-800 text-ink-300",
        tone === "ok" && "bg-emerald-500/15 text-emerald-300",
        tone === "warn" && "bg-amber-500/15 text-amber-300",
        tone === "error" && "bg-red-500/15 text-red-300",
        tone === "brand" && "bg-brand-500/15 text-brand-300",
        tone === "info" && "bg-sky-500/15 text-sky-300",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-[11px] font-semibold tracking-[0.12em] text-ink-400 uppercase">{children}</h3>
      {action}
    </div>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-xl border border-ink-800 bg-ink-900/70 p-3.5", className)}>{children}</div>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "ok" | "warn" | "error";
}) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/60 px-3 py-2.5">
      <div className="text-[11px] text-ink-400">{label}</div>
      <div
        className={cx(
          "mt-0.5 text-lg font-semibold tabular-nums",
          tone === "ok" && "text-emerald-300",
          tone === "warn" && "text-amber-300",
          tone === "error" && "text-red-300",
        )}
      >
        {value}
      </div>
      {hint && <div className="text-[11px] text-ink-400">{hint}</div>}
    </div>
  );
}

export function SeverityIcon({ severity, className }: { severity: Severity; className?: string }) {
  const cls = cx("size-4 shrink-0", className);
  if (severity === "pass") return <CircleCheck className={cx(cls, "text-emerald-400")} />;
  if (severity === "info") return <Info className={cx(cls, "text-sky-400")} />;
  if (severity === "warning") return <TriangleAlert className={cx(cls, "text-amber-400")} />;
  return <CircleX className={cx(cls, "text-red-400")} />;
}

export function AutoFixChip() {
  return (
    <Badge tone="brand">
      <Sparkles className="size-3" /> auto-fixed
    </Badge>
  );
}

/** Horizontal utilisation bar: `value` of `max`, coloured by how close to the limit it is. */
export function UsageBar({ value, max, label }: { value: number; max: number; label?: string }) {
  const ratio = max > 0 ? value / max : 1;
  const color = ratio > 1 ? "bg-red-400" : ratio > 0.9 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-800">
        <div
          className={cx("h-full rounded-full transition-[width] duration-300", color)}
          style={{ width: `${Math.min(ratio, 1) * 100}%` }}
        />
      </div>
      {label && <span className="w-10 text-right text-[11px] text-ink-300 tabular-nums">{label}</span>}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  size = "md",
}: {
  value: T;
  options: { value: T; label: ReactNode; disabled?: boolean; title?: string }[];
  onChange: (v: T) => void;
  size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex rounded-lg border border-ink-800 bg-ink-900 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          title={o.title}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={cx(
            "inline-flex items-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
            size === "sm" ? "px-2 py-1 text-[11px]" : "px-3 py-1.5 text-xs",
            value === o.value ? "bg-ink-700 text-ink-100 shadow-sm" : "text-ink-400 hover:text-ink-100",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 py-1 text-xs text-ink-300">
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative h-5 w-9 shrink-0 rounded-full transition-colors",
          checked ? "bg-brand-500" : "bg-ink-700",
        )}
      >
        <span
          className={cx(
            "absolute top-0.5 left-0 size-4 rounded-full bg-white transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </button>
    </label>
  );
}

export function RangeInput({
  value,
  min,
  max,
  step,
  onChange,
  ariaLabel,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  ariaLabel: string;
}) {
  const fill = max > min ? ((value - min) / (max - min)) * 100 : 0;
  return (
    <input
      type="range"
      className="rc-range"
      aria-label={ariaLabel}
      min={min}
      max={max}
      step={step}
      value={value}
      style={{ "--fill": `${Math.min(Math.max(fill, 0), 100)}%` } as React.CSSProperties}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  );
}
