"use client";

import { motion } from "framer-motion";
import { X, Edit2 } from "lucide-react";
import type { ICPFilters, ICPFilterChip } from "@/types";
import { cn } from "@/lib/utils";

interface ICPParameterSummaryProps {
  filters: ICPFilters;
  onRemoveChip?: (category: keyof ICPFilters, value: string) => void;
  className?: string;
}

const CATEGORY_LABELS: Partial<Record<keyof ICPFilters, string>> = {
  locations: "Locations",
  jobTitles: "Job Titles",
  industry: "Industry",
  companySize: "Company Size",
  revenue: "Revenue",
  technology: "Technology",
  keywords: "Keywords",
};

const CATEGORY_COLORS: Partial<Record<keyof ICPFilters, { color: string; bg: string; border: string }>> = {
  locations: { color: "#3b82f6", bg: "rgba(59,130,246,0.1)", border: "rgba(59,130,246,0.2)" },
  jobTitles: { color: "#a855f7", bg: "rgba(168,85,247,0.1)", border: "rgba(168,85,247,0.2)" },
  industry: { color: "#06b6d4", bg: "rgba(6,182,212,0.1)", border: "rgba(6,182,212,0.2)" },
  companySize: { color: "#eab308", bg: "rgba(234,179,8,0.1)", border: "rgba(234,179,8,0.2)" },
  revenue: { color: "#22c55e", bg: "rgba(34,197,94,0.1)", border: "rgba(34,197,94,0.2)" },
  technology: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.2)" },
  keywords: { color: "#64748b", bg: "rgba(100,116,139,0.1)", border: "rgba(100,116,139,0.2)" },
};

function FilterChip({
  chip,
  color,
  bg,
  border,
  onRemove,
}: {
  chip: ICPFilterChip;
  color: string;
  bg: string;
  border: string;
  onRemove?: () => void;
}) {
  return (
    <motion.span
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all hover:brightness-110"
      style={{ color, background: bg, border: `1px solid ${border}` }}
    >
      {chip.label}
      {chip.removable && onRemove && (
        <button
          onClick={onRemove}
          className="ml-0.5 hover:opacity-70 transition-opacity"
          aria-label={`Remove ${chip.label}`}
        >
          <X size={10} />
        </button>
      )}
    </motion.span>
  );
}

export function ICPParameterSummary({
  filters,
  onRemoveChip,
  className,
}: ICPParameterSummaryProps) {
  const categories = Object.entries(CATEGORY_LABELS) as [keyof ICPFilters, string][];

  return (
    <div
      className={cn("rounded-xl p-4", className)}
      style={{
        background: "var(--apex-surface)",
        border: "1px solid var(--apex-border)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold" style={{ color: "var(--apex-text)" }}>
            AI-Generated ICP Parameters
          </span>
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(59,130,246,0.1)",
              color: "var(--apex-accent)",
              border: "1px solid rgba(59,130,246,0.2)",
            }}
          >
            Edit or refine
          </span>
        </div>
        <button
          className="flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-white/5 transition-colors text-xs"
          style={{ color: "var(--apex-muted)", border: "1px solid var(--apex-border)" }}
          aria-label="Edit ICP parameters"
        >
          <Edit2 size={11} />
          Edit
        </button>
      </div>

      {/* Filter rows */}
      <div className="space-y-3">
        {categories.map(([key, label]) => {
          const chips = filters[key] as ICPFilterChip[];
          const style = CATEGORY_COLORS[key];
          if (!chips || chips.length === 0 || !style) return null;

          return (
            <div key={key} className="flex items-start gap-3">
              <span
                className="text-xs font-medium flex-shrink-0 pt-1 w-24"
                style={{ color: "var(--apex-muted)" }}
              >
                {label}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {chips.map((chip) => (
                  <FilterChip
                    key={chip.value}
                    chip={chip}
                    color={style.color}
                    bg={style.bg}
                    border={style.border}
                    onRemove={() => onRemoveChip?.(key, chip.value)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
