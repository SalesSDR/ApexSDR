"use client";

import { useMemo, useState } from "react";
import { Search, User, ChevronDown } from "lucide-react";
import { useProspectDirectory, type DirectoryProspect } from "@/hooks/useProspectDirectory";

interface ProspectPickerProps {
  value: DirectoryProspect | null;
  onChange: (prospect: DirectoryProspect | null) => void;
  placeholder?: string;
}

export function ProspectPicker({ value, onChange, placeholder = "Search prospects by name or email…" }: ProspectPickerProps) {
  const { prospects, isLoading, error } = useProspectDirectory();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    if (!query.trim()) return prospects.slice(0, 25);
    const q = query.toLowerCase();
    return prospects.filter((p) => p.name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q)).slice(0, 25);
  }, [prospects, query]);

  return (
    <div className="relative w-full max-w-sm">
      <div
        className="flex items-center gap-2 rounded-lg px-3 py-2"
        style={{ background: "var(--apex-surface-2)", border: "1px solid var(--apex-border)" }}
      >
        <Search size={14} style={{ color: "var(--apex-muted)" }} />
        <input
          value={value ? value.name : query}
          onChange={(e) => {
            onChange(null);
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm outline-none"
          style={{ color: "var(--apex-text)" }}
        />
        <ChevronDown size={14} style={{ color: "var(--apex-muted)" }} />
      </div>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-lg py-1 shadow-2xl"
            style={{ background: "var(--apex-surface-3)", border: "1px solid var(--apex-border-light)" }}
          >
            {isLoading && (
              <div className="px-3 py-2 text-xs" style={{ color: "var(--apex-text-dim)" }}>
                Loading prospects…
              </div>
            )}
            {error && (
              <div className="px-3 py-2 text-xs" style={{ color: "var(--apex-danger)" }}>
                {error}
              </div>
            )}
            {!isLoading && !error && filtered.length === 0 && (
              <div className="px-3 py-2 text-xs" style={{ color: "var(--apex-text-dim)" }}>
                No prospects match &quot;{query}&quot;.
              </div>
            )}
            {filtered.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  onChange(p);
                  setQuery("");
                  setOpen(false);
                }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-white/5"
                style={{ color: "var(--apex-text)" }}
              >
                <User size={13} style={{ color: "var(--apex-muted)" }} />
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                <span className="flex-shrink-0 text-xs" style={{ color: "var(--apex-text-faint)" }}>
                  {p.status}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
