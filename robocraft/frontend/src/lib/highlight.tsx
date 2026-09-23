import type { ReactNode } from "react";
import type { Language } from "./types";

// A tiny tokenizer - enough to make generated firmware readable without a heavy dependency.
const CPP = new RegExp(
  [
    String.raw`(?<comment>\/\/[^\n]*|\/\*[\s\S]*?\*\/)`,
    String.raw`(?<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)')`,
    String.raw`(?<preproc>^#\w+[^\n]*)`,
    String.raw`(?<number>\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?:f|UL|L)?\b)`,
    String.raw`(?<keyword>\b(?:const|float|int|bool|void|if|else|for|while|return|struct|unsigned|long|char|true|false|sizeof|break|static)\b)`,
    String.raw`(?<type>\b(?:Servo|ESP32PWM|HIGH|LOW|OUTPUT|INPUT|Serial)\b)`,
    String.raw`(?<call>\b[A-Za-z_]\w*(?=\())`,
  ].join("|"),
  "gm",
);

const PY = new RegExp(
  [
    String.raw`(?<string>"""[\s\S]*?"""|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')`,
    String.raw`(?<comment>#[^\n]*)`,
    String.raw`(?<number>\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b)`,
    String.raw`(?<keyword>\b(?:def|class|return|if|elif|else|for|while|in|import|from|as|True|False|None|and|or|not|try|except|global|with|lambda|pass|break|continue|is)\b)`,
    String.raw`(?<type>\b(?:Pin|PWM|Servo|self)\b)`,
    String.raw`(?<call>\b[A-Za-z_]\w*(?=\())`,
  ].join("|"),
  "gm",
);

const CLASSES: Record<string, string> = {
  comment: "text-ink-400 italic",
  string: "text-emerald-300",
  preproc: "text-fuchsia-300",
  number: "text-amber-300",
  keyword: "text-sky-300",
  type: "text-violet-300",
  call: "text-brand-300",
};

export function highlight(code: string, language: Language): ReactNode[] {
  const pattern = language === "arduino" ? CPP : PY;
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of code.matchAll(pattern)) {
    const index = m.index ?? 0;
    if (index > last) out.push(code.slice(last, index));
    const group = Object.entries(m.groups ?? {}).find(([, v]) => v !== undefined)?.[0];
    out.push(
      <span key={key++} className={group ? CLASSES[group] : undefined}>
        {m[0]}
      </span>,
    );
    last = index + m[0].length;
  }
  if (last < code.length) out.push(code.slice(last));
  return out;
}
