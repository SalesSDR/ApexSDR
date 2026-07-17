"use client";

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="w-full">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-5 py-3.5 border-b"
          style={{ borderColor: "var(--apex-border)", animationDelay: `${i * 0.05}s` }}
        >
          {/* Checkbox */}
          <div className="skeleton w-4 h-4 rounded flex-shrink-0" />
          {/* Avatar */}
          <div className="skeleton w-8 h-8 rounded-full flex-shrink-0" />
          {/* Name + title */}
          <div className="flex flex-col gap-1.5 flex-1 min-w-0" style={{ maxWidth: 180 }}>
            <div className="skeleton h-3 rounded" style={{ width: "70%" }} />
            <div className="skeleton h-2.5 rounded" style={{ width: "50%" }} />
          </div>
          {/* LinkedIn chip */}
          <div className="skeleton h-5 w-28 rounded-full flex-shrink-0" />
          {/* Email chip */}
          <div className="skeleton h-5 w-24 rounded-full flex-shrink-0" />
          {/* Call chip */}
          <div className="skeleton h-5 w-20 rounded-full flex-shrink-0" />
          {/* Last activity */}
          <div className="skeleton h-3 w-16 rounded flex-shrink-0" />
          {/* Actions */}
          <div className="flex gap-2 flex-shrink-0">
            <div className="skeleton w-6 h-6 rounded" />
            <div className="skeleton w-6 h-6 rounded" />
            <div className="skeleton w-6 h-6 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ICPWidgetSkeleton() {
  return (
    <div
      className="rounded-xl p-5 space-y-4"
      style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
    >
      <div className="skeleton h-4 w-40 rounded" />
      <div className="skeleton h-16 rounded-lg" />
      <div className="flex gap-2">
        {[120, 100, 110].map((w, i) => (
          <div key={i} className="skeleton h-6 rounded-full" style={{ width: w }} />
        ))}
      </div>
    </div>
  );
}

export function FilterChipSkeleton() {
  return (
    <div className="flex flex-wrap gap-2">
      {[80, 100, 70, 90, 60, 110, 75].map((w, i) => (
        <div key={i} className="skeleton h-6 rounded-full" style={{ width: w }} />
      ))}
    </div>
  );
}
