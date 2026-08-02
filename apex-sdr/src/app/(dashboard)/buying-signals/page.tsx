"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { Flame, Search, Radar, Zap } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { fetchApi } from "@/lib/api";
import { useProspectDirectory } from "@/hooks/useProspectDirectory";
import { EmptyState, ErrorState, RowsSkeleton, CardsSkeleton } from "@/components/ui/DataStates";
import { Pill, type PillTone } from "@/components/ui/Pill";
import { SummaryCard, FilterSelect, SearchInput, Th, ThSortable, Pagination } from "@/components/shared/TableBits";
import { formatDateTime, formatRelativeTime, titleCase } from "@/lib/format";

interface BuyingSignal {
  id: string;
  prospect_id: string;
  signal_type: string;
  signal_source: string;
  signal_strength: "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";
  confidence: number;
  summary: string;
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
}

const STRENGTH_TONE: Record<string, PillTone> = {
  LOW: "neutral",
  MEDIUM: "cyan",
  HIGH: "gold",
  VERY_HIGH: "danger",
};
const STRENGTH_RANK: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2, VERY_HIGH: 3 };
const PAGE_SIZE = 15;
type SortKey = "created_at" | "confidence" | "signal_strength";

export default function BuyingSignalsPage() {
  const { data, error, isLoading, mutate } = useSWR("/signals?limit=200", fetchApi);
  const { byId } = useProspectDirectory();

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [strengthFilter, setStrengthFilter] = useState("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const signals: BuyingSignal[] = useMemo(() => data?.data ?? [], [data]);
  const signalTypes = useMemo(() => Array.from(new Set(signals.map((s) => s.signal_type))).sort(), [signals]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = signals.filter((s) => {
      const prospectName = byId.get(s.prospect_id)?.name ?? "";
      const matchesSearch =
        !q || s.summary.toLowerCase().includes(q) || prospectName.toLowerCase().includes(q) || s.signal_source.toLowerCase().includes(q);
      const matchesType = typeFilter === "ALL" || s.signal_type === typeFilter;
      const matchesStrength = strengthFilter === "ALL" || s.signal_strength === strengthFilter;
      return matchesSearch && matchesType && matchesStrength;
    });

    return [...rows].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "created_at") cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      else if (sortKey === "confidence") cmp = a.confidence - b.confidence;
      else cmp = STRENGTH_RANK[a.signal_strength] - STRENGTH_RANK[b.signal_strength];
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [signals, search, typeFilter, strengthFilter, sortKey, sortDir, byId]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);
  const strongCount = signals.filter((s) => s.signal_strength === "HIGH" || s.signal_strength === "VERY_HIGH").length;
  const mostRecent = signals[0];

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
          <Radar size={20} style={{ color: "var(--apex-accent)" }} />
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>
              Buying Signals
            </h1>
            <p className="text-xs" style={{ color: "var(--apex-muted)" }}>
              Active intent signals collected across your prospect base.
            </p>
          </div>
        </div>

        {error ? (
          <ErrorState message={error instanceof Error ? error.message : "Failed to load buying signals."} onRetry={() => mutate()} />
        ) : isLoading ? (
          <>
            <CardsSkeleton count={3} />
            <div className="mt-6 rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
              <RowsSkeleton rows={6} cols={5} />
            </div>
          </>
        ) : signals.length === 0 ? (
          <EmptyState
            icon={<Radar size={18} />}
            title="No buying signals yet"
            description="The pipeline hasn't collected any buying signals for your prospects yet. Signals appear here once collected via the signal provider or added manually."
          />
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <SummaryCard label="Active Signals" value={signals.length.toLocaleString()} icon={<Zap size={12} />} />
              <SummaryCard label="Strong Signals (HIGH/VERY HIGH)" value={strongCount.toLocaleString()} icon={<Flame size={12} />} />
              <SummaryCard label="Most Recent" value={mostRecent ? formatRelativeTime(mostRecent.created_at) : "—"} />
            </div>

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <SearchInput
                value={search}
                onChange={(v) => {
                  setSearch(v);
                  setPage(1);
                }}
                placeholder="Search summary, prospect, or source…"
                icon={<Search size={14} style={{ color: "var(--apex-muted)" }} />}
              />
              <FilterSelect
                value={typeFilter}
                onChange={(v) => {
                  setTypeFilter(v);
                  setPage(1);
                }}
                options={[{ value: "ALL", label: "All types" }, ...signalTypes.map((t) => ({ value: t, label: titleCase(t) }))]}
              />
              <FilterSelect
                value={strengthFilter}
                onChange={(v) => {
                  setStrengthFilter(v);
                  setPage(1);
                }}
                options={[
                  { value: "ALL", label: "All strengths" },
                  { value: "VERY_HIGH", label: "Very High" },
                  { value: "HIGH", label: "High" },
                  { value: "MEDIUM", label: "Medium" },
                  { value: "LOW", label: "Low" },
                ]}
              />
            </div>

            {filtered.length === 0 ? (
              <EmptyState title="No signals match your filters" description="Try clearing the search or filters above." />
            ) : (
              <div className="overflow-hidden rounded-xl" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--apex-border)" }}>
                        <Th>Prospect</Th>
                        <Th>Type</Th>
                        <ThSortable label="Strength" active={sortKey === "signal_strength"} dir={sortDir} onClick={() => toggleSort("signal_strength")} />
                        <ThSortable label="Confidence" active={sortKey === "confidence"} dir={sortDir} onClick={() => toggleSort("confidence")} />
                        <Th>Summary</Th>
                        <ThSortable label="Detected" active={sortKey === "created_at"} dir={sortDir} onClick={() => toggleSort("created_at")} />
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((s) => (
                        <tr key={s.id} className="table-row-hover" style={{ borderBottom: "1px solid var(--apex-border)" }}>
                          <td className="px-4 py-3 whitespace-nowrap" style={{ color: "var(--apex-text)" }}>
                            {byId.get(s.prospect_id)?.name ?? s.prospect_id.slice(0, 8)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {titleCase(s.signal_type)}
                          </td>
                          <td className="px-4 py-3">
                            <Pill tone={STRENGTH_TONE[s.signal_strength] ?? "neutral"}>{titleCase(s.signal_strength)}</Pill>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: "var(--apex-text-dim)" }}>
                            {Math.round(s.confidence * 100)}%
                          </td>
                          <td className="max-w-xs truncate px-4 py-3 text-xs" style={{ color: "var(--apex-text-dim)" }} title={s.summary}>
                            {s.summary}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-xs" style={{ color: "var(--apex-text-faint)" }} title={formatDateTime(s.created_at)}>
                            {formatRelativeTime(s.created_at)}
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
