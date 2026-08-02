"use client";

import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-xl py-14 px-6 text-center"
      style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
    >
      <div
        className="flex h-10 w-10 items-center justify-center rounded-full"
        style={{ background: "var(--apex-danger-dim)", color: "var(--apex-danger)" }}
      >
        <AlertTriangle size={18} />
      </div>
      <p className="text-sm font-medium" style={{ color: "var(--apex-text)" }}>
        Couldn&apos;t load this data
      </p>
      <p className="max-w-sm text-xs" style={{ color: "var(--apex-text-dim)" }}>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
          style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)", color: "var(--apex-text-dim)" }}
        >
          <RefreshCw size={12} />
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 rounded-xl py-14 px-6 text-center"
      style={{ background: "var(--apex-surface)", border: "1px dashed var(--apex-border)" }}
    >
      <div
        className="mb-1 flex h-10 w-10 items-center justify-center rounded-full"
        style={{ background: "var(--apex-surface-2)", color: "var(--apex-muted)" }}
      >
        {icon ?? <Inbox size={18} />}
      </div>
      <p className="text-sm font-medium" style={{ color: "var(--apex-text)" }}>
        {title}
      </p>
      {description && (
        <p className="max-w-sm text-xs" style={{ color: "var(--apex-text-dim)" }}>
          {description}
        </p>
      )}
      {action}
    </div>
  );
}

export function RowsSkeleton({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="w-full">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-5 py-3.5 border-b"
          style={{ borderColor: "var(--apex-border)" }}
        >
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="skeleton h-3 rounded flex-1"
              style={{ maxWidth: c === 0 ? 160 : undefined, animationDelay: `${(i * cols + c) * 0.03}s` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl p-4"
          style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}
        >
          <div className="skeleton mb-3 h-3 w-20 rounded" />
          <div className="skeleton h-6 w-16 rounded" />
        </div>
      ))}
    </div>
  );
}
