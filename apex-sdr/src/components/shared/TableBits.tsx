"use client";

import { ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import type { PillTone } from "@/components/ui/Pill";

export function SummaryCard({ label, value, icon, tone }: { label: string; value: string; icon?: ReactNode; tone?: PillTone }) {
  void tone;
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
      <div className="mb-2 flex items-center gap-1.5 text-xs" style={{ color: "var(--apex-muted)" }}>
        {icon}
        {label}
      </div>
      <p className="text-xl font-bold" style={{ color: "var(--apex-text)" }}>
        {value}
      </p>
    </div>
  );
}

export function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg px-3 py-2 text-xs outline-none"
      style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)", color: "var(--apex-text-dim)" }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} style={{ background: "var(--apex-surface-2)" }}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  icon,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  icon: ReactNode;
}) {
  return (
    <div
      className="flex min-w-[220px] flex-1 items-center gap-2 rounded-lg px-3 py-2"
      style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
    >
      {icon}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent text-sm outline-none"
        style={{ color: "var(--apex-text)" }}
      />
    </div>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th className="px-4 py-2.5 text-xs font-medium whitespace-nowrap" style={{ color: "var(--apex-muted)" }}>
      {children}
    </th>
  );
}

export function ThSortable({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: "asc" | "desc";
  onClick: () => void;
}) {
  return (
    <th className="px-4 py-2.5 text-xs font-medium whitespace-nowrap">
      <button onClick={onClick} className="flex items-center gap-1" style={{ color: active ? "var(--apex-accent)" : "var(--apex-muted)" }}>
        {label}
        <ArrowUpDown size={11} style={{ transform: active && dir === "asc" ? "scaleY(-1)" : undefined }} />
      </button>
    </th>
  );
}

export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="flex items-center justify-between px-4 py-3 text-xs" style={{ borderTop: "1px solid var(--apex-border)", color: "var(--apex-muted)" }}>
      <span>
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(Math.max(1, page - 1))}
          disabled={page === 1}
          className="rounded p-1 disabled:opacity-30"
          style={{ color: "var(--apex-text-dim)" }}
          aria-label="Previous page"
        >
          <ChevronLeft size={14} />
        </button>
        <span style={{ color: "var(--apex-text-dim)" }}>
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onChange(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
          className="rounded p-1 disabled:opacity-30"
          style={{ color: "var(--apex-text-dim)" }}
          aria-label="Next page"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
