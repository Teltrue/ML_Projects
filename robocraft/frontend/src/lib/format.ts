export const usd = (v: number) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export const mm = (m: number, digits = 0) => `${(m * 1000).toFixed(digits)} mm`;

export const kgcm = (v: number) => `${v < 10 ? v.toFixed(2) : v.toFixed(1)} kg·cm`;

export const pct = (v: number) => `${Math.round(v * 100)}%`;

export const mass = (kg: number) => (kg < 1 ? `${Math.round(kg * 1000)} g` : `${kg.toFixed(2)} kg`);

export const deg = (v: number, digits = 1) => `${v.toFixed(digits)}°`;

export function trimNumber(v: number, step: number | null) {
  if (!step) return String(Number(v.toFixed(3)));
  const decimals = Math.max(0, Math.ceil(-Math.log10(step) - 1e-9));
  return v.toFixed(Math.min(decimals, 3));
}
