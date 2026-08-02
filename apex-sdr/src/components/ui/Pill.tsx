"use client";

import type { ReactNode } from "react";

export type PillTone = "neutral" | "success" | "warning" | "danger" | "accent" | "purple" | "cyan" | "gold";

const TONE_VARS: Record<PillTone, { color: string; bg: string }> = {
  neutral: { color: "var(--apex-muted-light)", bg: "rgba(100,116,139,0.12)" },
  success: { color: "var(--apex-success)", bg: "var(--apex-success-dim)" },
  warning: { color: "var(--apex-warning)", bg: "var(--apex-warning-dim)" },
  danger: { color: "var(--apex-danger)", bg: "var(--apex-danger-dim)" },
  accent: { color: "var(--apex-accent)", bg: "var(--apex-accent-glow)" },
  purple: { color: "var(--apex-purple)", bg: "var(--apex-purple-dim)" },
  cyan: { color: "var(--apex-cyan)", bg: "var(--apex-cyan-dim)" },
  gold: { color: "var(--apex-gold)", bg: "var(--apex-gold-dim)" },
};

export function Pill({ tone = "neutral", icon, children }: { tone?: PillTone; icon?: ReactNode; children: ReactNode }) {
  const v = TONE_VARS[tone];
  return (
    <span
      className="inline-flex w-fit items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ color: v.color, background: v.bg }}
    >
      {icon}
      {children}
    </span>
  );
}
