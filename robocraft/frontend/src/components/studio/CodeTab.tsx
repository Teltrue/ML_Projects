"use client";

import { Check, Copy, Download, LoaderCircle, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { highlight } from "@/lib/highlight";
import { useStudio } from "@/lib/store";
import type { Language, RoverPreset } from "@/lib/types";
import { Button, SectionTitle, Segmented } from "../ui";
import { download } from "./ElectronicsTab";

// Module-level so the selector fallback is referentially stable.
const ARDUINO_ONLY: Language[] = ["arduino"];

export default function CodeTab() {
  const code = useStudio((s) => s.code);
  const loading = useStudio((s) => s.codeLoading);
  const error = useStudio((s) => s.codeError);
  const language = useStudio((s) => s.language);
  const template = useStudio((s) => s.design?.template);
  const languages = useStudio((s) => s.analysis?.electrical.board.languages) ?? ARDUINO_ONLY;
  const boardName = useStudio((s) => s.analysis?.electrical.board.name);
  const preset = useStudio((s) => s.roverPreset);
  const [copied, setCopied] = useState(false);

  const highlighted = useMemo(() => (code ? highlight(code.code, code.language) : null), [code]);
  const lineCount = code ? code.code.split("\n").length : 0;

  const copy = async () => {
    if (!code) return;
    await navigator.clipboard.writeText(code.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented<Language>
          value={language}
          onChange={(v) => useStudio.setState({ language: v })}
          options={[
            { value: "arduino", label: "Arduino C++" },
            {
              value: "micropython",
              label: "MicroPython",
              disabled: !languages.includes("micropython"),
              title: languages.includes("micropython")
                ? undefined
                : `MicroPython doesn't run on the ${boardName}; pick an ESP32 or Pico.`,
            },
          ]}
        />
        {template === "rover" && (
          <Segmented<RoverPreset>
            size="sm"
            value={preset}
            onChange={(v) => useStudio.setState({ roverPreset: v })}
            options={[
              { value: "square", label: "Square" },
              { value: "figure8", label: "Figure-8" },
              { value: "spin", label: "Spin" },
            ]}
          />
        )}
        {loading && <LoaderCircle className="size-4 animate-spin text-ink-400" />}
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-200">
          <TriangleAlert className="mt-px size-4 shrink-0" /> {error}
        </div>
      )}

      {code && (
        <>
          {code.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-100">
              <div className="mb-1 flex items-center gap-1.5 font-medium">
                <TriangleAlert className="size-4" /> Fix these design errors before building:
              </div>
              <ul className="list-disc pl-5">
                {code.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          <section>
            <SectionTitle>Flash it</SectionTitle>
            <ol className="list-decimal space-y-1 pl-5 text-xs leading-relaxed text-ink-300">
              {code.instructions.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </section>
          <section>
            <SectionTitle
              action={
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={copy}>
                    {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
                    {copied ? "Copied" : "Copy"}
                  </Button>
                  <Button size="sm" onClick={() => download(code.filename, code.code)}>
                    <Download className="size-3" /> {code.filename}
                  </Button>
                </div>
              }
            >
              {code.language_label} · {code.board}
            </SectionTitle>
            <div className="rc-scroll max-h-[60vh] overflow-auto rounded-xl border border-ink-800 bg-ink-950">
              <div className="flex min-w-max font-mono text-[11px] leading-[1.55]">
                <pre
                  aria-hidden
                  className="sticky left-0 border-r border-ink-800 bg-ink-950 px-2 py-3 text-right text-ink-600 select-none"
                >
                  {Array.from({ length: lineCount }, (_, i) => i + 1).join("\n")}
                </pre>
                <pre className="px-3 py-3 text-ink-100">
                  <code>{highlighted}</code>
                </pre>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
