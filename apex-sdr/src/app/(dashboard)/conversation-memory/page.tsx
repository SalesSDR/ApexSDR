"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { BrainCircuit, Search, CheckCircle2, Circle } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { fetchApi } from "@/lib/api";
import { ProspectPicker } from "@/components/shared/ProspectPicker";
import type { DirectoryProspect } from "@/hooks/useProspectDirectory";
import { EmptyState, ErrorState, RowsSkeleton } from "@/components/ui/DataStates";
import { Pill, type PillTone } from "@/components/ui/Pill";
import { FilterSelect, SearchInput, Th, ThSortable, Pagination } from "@/components/shared/TableBits";
import { formatDateTime, formatRelativeTime, titleCase } from "@/lib/format";

interface ConversationMemory {
  id: string;
  memory_type: string;
  content: string;
  importance_score: number;
  is_resolved: boolean;
  source: string;
  created_by: string | null;
  expires_at: string | null;
  created_at: string;
}

const MEMORY_TYPES = ["LINKEDIN_MESSAGE", "EMAIL_MESSAGE", "CALL_SUMMARY", "AI_NOTE", "OBJECTION", "PREFERENCE", "MEETING_OUTCOME", "BUYING_SIGNAL"];

const MEMORY_TONE: Record<string, PillTone> = {
  LINKEDIN_MESSAGE: "accent",
  EMAIL_MESSAGE: "cyan",
  CALL_SUMMARY: "purple",
  AI_NOTE: "neutral",
  OBJECTION: "danger",
  PREFERENCE: "gold",
  MEETING_OUTCOME: "success",
  BUYING_SIGNAL: "warning",
};

const PAGE_SIZE = 15;
type SortKey = "created_at" | "importance_score";

export default function ConversationMemoryPage() {
  const [prospect, setProspect] = useState<DirectoryProspect | null>(null);
  const [memoryType, setMemoryType] = useState("ALL");
  const [limit, setLimit] = useState(50);
  const [search, setSearch] = useState("");
  const [resolvedFilter, setResolvedFilter] = useState("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const endpoint = prospect
    ? `/prospects/${prospect.id}/memory?limit=${limit}${memoryType !== "ALL" ? `&memory_type=${memoryType}` : ""}`
    : null;
  const { data, error, isLoading, mutate } = useSWR(endpoint, fetchApi);

  const memories: ConversationMemory[] = useMemo(() => data?.data ?? [], [data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = memories.filter((m) => {
      const matchesSearch = !q || m.content.toLowerCase().includes(q) || m.source.toLowerCase().includes(q);
      const matchesResolved = resolvedFilter === "ALL" || (resolvedFilter === "RESOLVED" ? m.is_resolved : !m.is_resolved);
      return matchesSearch && matchesResolved;
    });
    return [...rows].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "created_at") cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      else cmp = a.importance_score - b.importance_score;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [memories, search, resolvedFilter, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="flex h-full flex-col">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="mb-6 flex items-center gap-2">
          <BrainCircuit size={20} style={{ color: "var(--apex-accent)" }} />
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
              Conversation Memory
            </h1>
            <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
              Everything the AI remembers about a prospect across every channel.
            </p>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: "var(--apex-text-dim)" }}>
              Prospect
            </label>
            <ProspectPicker value={prospect} onChange={setProspect} />
          </div>
          {prospect && (
            <FilterSelect
              value={memoryType}
              onChange={(v) => {
                setMemoryType(v);
                setPage(1);
              }}
              options={[{ value: "ALL", label: "All memory types" }, ...MEMORY_TYPES.map((t) => ({ value: t, label: titleCase(t) }))]}
            />
          )}
        </div>

        {!prospect ? (
          <EmptyState
            icon={<BrainCircuit size={18} />}
            title="Select a prospect to view its conversation memory"
            description="Conversation memory is per-prospect — search for someone above to see everything the AI has recorded about them."
          />
        ) : error ? (
          <ErrorState message={error instanceof Error ? error.message : "Failed to load conversation memory."} onRetry={() => mutate()} />
        ) : isLoading ? (
          <div className="rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
            <RowsSkeleton rows={6} cols={4} />
          </div>
        ) : memories.length === 0 ? (
          <EmptyState title="No conversation memory yet for this prospect" description="Memories are recorded as the AI interacts with this prospect across channels." />
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(1);
                }}
                placeholder="Search content or source…"
                icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
              />
              <FilterSelect
                value={resolvedFilter}
                onChange={(v) => {
                  setResolvedFilter(v);
                  setPage(1);
                }}
                options={[
                  { value: "ALL", label: "Resolved & Open" },
                  { value: "RESOLVED", label: "Resolved only" },
                  { value: "OPEN", label: "Open only" },
                ]}
              />
              <FilterSelect
                value={String(limit)}
                onChange={(v) => {
                  setLimit(Number(v));
                  setPage(1);
                }}
                options={[
                  { value: "50", label: "Last 50" },
                  { value: "100", label: "Last 100" },
                  { value: "200", label: "Last 200" },
                ]}
              />
            </div>

            {filtered.length === 0 ? (
              <EmptyState title="No memories match your filters" />
            ) : (
              <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-left text-sm">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                        <Th>Type</Th>
                        <Th>Content</Th>
                        <ThSortable label="Importance" active={sortKey === "importance_score"} dir={sortDir} onClick={() => toggleSort("importance_score")} />
                        <Th>Status</Th>
                        <Th>Source</Th>
                        <ThSortable label="When" active={sortKey === "created_at"} dir={sortDir} onClick={() => toggleSort("created_at")} />
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((m) => (
                        <tr key={m.id} className="table-row-hover" style={{ borderBottom: "1px solid var(--apex-border)" }}>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <Pill tone={MEMORY_TONE[m.memory_type] ?? "neutral"}>{titleCase(m.memory_type)}</Pill>
                          </td>
                          <td className="max-w-sm truncate px-4 py-3 text-xs" style={{ color: "var(--apex-text-dim)" }} title={m.content}>
                            {m.content}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {m.importance_score}/10
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {m.is_resolved ? (
                              <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--apex-success)" }}>
                                <CheckCircle2 size={12} /> Resolved
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--apex-text-faint)" }}>
                                <Circle size={12} /> Open
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-faint)" }}>
                            {m.source}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(m.created_at)}>
                            {formatRelativeTime(m.created_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination page={clampedPage} totalPages={totalPages} total={filtered.length} pageSize={PAGE_SIZE} onChange={setPage} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
